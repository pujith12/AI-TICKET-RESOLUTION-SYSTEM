import hashlib
import json
import logging
import re
import urllib.error
import urllib.request

import pandas as pd

import config
import database
import llm_engine
import rag_engine

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "i",
    "if", "in", "is", "it", "my", "of", "on", "or", "please", "the", "to", "was",
    "what", "when", "where", "with", "you", "your",
}


def normalize_ticket_text(title, description):
    title_tokens = re.sub(r"[^a-z0-9\s]", " ", title.lower()).split()
    description_tokens = re.sub(r"[^a-z0-9\s]", " ", description.lower()).split()
    title_tokens = [token for token in title_tokens if token and token not in STOP_WORDS]
    description_tokens = [token for token in description_tokens if token and token not in STOP_WORDS]

    prioritized_tokens = []
    for token in title_tokens + description_tokens:
        if token not in prioritized_tokens:
            prioritized_tokens.append(token)

    normalized = " ".join(prioritized_tokens[:6]).strip()
    return normalized or "general support request"


def build_gap_group_key(category, normalized_query):
    core_phrase = " ".join(normalized_query.split()[:3]) or normalized_query
    payload = f"{category.lower()}::{core_phrase}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def suggest_kb_filename(normalized_query):
    tokens = re.findall(r"[a-z0-9]+", normalized_query)
    stem = "_".join(tokens[:6]) if tokens else "knowledge_gap"
    return f"{stem}_guide.md"


def get_gap_alert_threshold():
    return config.get_int_env("AI_GAP_ALERT_THRESHOLD", 3)


def get_slack_webhook_url():
    return (config.get_env("SLACK_WEBHOOK_URL", "") or "").strip()


def _send_slack_alert(event_row):
    slack_webhook_url = get_slack_webhook_url()
    if not slack_webhook_url:
        return {
            "status": "skipped",
            "message": "Slack webhook not configured.",
        }

    payload = json.dumps(
        {
            "text": (
                "⚠ Knowledge Gap Detected\n"
                f"Top unresolved question: {event_row['display_query']}\n"
                f"Repeated: {event_row['occurrence_count']} times\n"
                f"Suggested action: Add knowledge file {event_row['suggested_kb_filename']}"
            )
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        slack_webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return {
                "status": "sent",
                "message": f"Slack alert delivered with HTTP {response.status}.",
            }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        logging.warning("Slack alert failed: %s", exc)
        return {
            "status": "failed",
            "message": str(exc),
        }


def _upsert_knowledge_gap(cursor, ticket_id, category, normalized_query, confidence_score, suggested_kb_filename):
    """Updates the existing knowledge gap table"""
    gap_alert_threshold = get_gap_alert_threshold()
    gap_group_key = build_gap_group_key(category, normalized_query)
    display_query = normalized_query.title()
    cursor.execute(
        """
        SELECT *
        FROM knowledge_gap_events
        WHERE gap_group_key = ?
        """,
        (gap_group_key,),
    )
    existing = cursor.fetchone()

    alert_result = None
    if existing:
        occurrence_count = existing["occurrence_count"] + 1
        avg_confidence = round(
            ((existing["avg_confidence_score"] * existing["occurrence_count"]) + confidence_score)
            / occurrence_count,
            3,
        )
        cursor.execute(
            """
            UPDATE knowledge_gap_events
            SET occurrence_count = ?,
                latest_ticket_id = ?,
                latest_confidence_score = ?,
                avg_confidence_score = ?,
                last_seen_at = CURRENT_TIMESTAMP,
                suggested_kb_filename = ?,
                category = ?,
                display_query = ?
            WHERE gap_group_key = ?
            """,
            (
                occurrence_count,
                ticket_id,
                confidence_score,
                avg_confidence,
                suggested_kb_filename,
                category,
                display_query,
                gap_group_key,
            ),
        )
        last_alert_count = existing["last_alert_count"] or 0
        if occurrence_count >= gap_alert_threshold and occurrence_count > last_alert_count:
            alert_result = _send_slack_alert(
                {
                    "display_query": display_query,
                    "occurrence_count": occurrence_count,
                    "suggested_kb_filename": suggested_kb_filename,
                }
            )
            cursor.execute(
                """
                UPDATE knowledge_gap_events
                SET last_alert_count = ?,
                    last_alert_status = ?,
                    last_alert_message = ?,
                    last_alert_at = CURRENT_TIMESTAMP
                WHERE gap_group_key = ?
                """,
                (
                    occurrence_count,
                    alert_result["status"],
                    alert_result["message"],
                    gap_group_key,
                ),
            )
    else:
        cursor.execute(
            """
            INSERT INTO knowledge_gap_events (
                gap_group_key,
                normalized_query,
                display_query,
                suggested_kb_filename,
                category,
                occurrence_count,
                latest_ticket_id,
                latest_confidence_score,
                avg_confidence_score
            )
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                gap_group_key,
                normalized_query,
                display_query,
                suggested_kb_filename,
                category,
                ticket_id,
                confidence_score,
                confidence_score,
            ),
        )
        if 1 >= gap_alert_threshold:
            alert_result = _send_slack_alert(
                {
                    "display_query": display_query,
                    "occurrence_count": 1,
                    "suggested_kb_filename": suggested_kb_filename,
                }
            )
            cursor.execute(
                """
                UPDATE knowledge_gap_events
                SET last_alert_count = ?,
                    last_alert_status = ?,
                    last_alert_message = ?,
                    last_alert_at = CURRENT_TIMESTAMP
                WHERE gap_group_key = ?
                """,
                (
                    1,
                    alert_result["status"],
                    alert_result["message"],
                    gap_group_key,
                ),
            )

    return gap_group_key, alert_result


def chat_with_ai(query: str, username: str) -> str:
    """Provides a quick generic AI chat response mapped directly to the local knowledge base."""
    # Reusing the existing resolution generator for the chat flow
    response = llm_engine.analyze_ticket(f"Chat Query: {query}", "User is asking via chat support", "Low", "General")
    return response.get("resolution_text", "I'm sorry, I couldn't process that request.")


def submit_ticket(title: str, description: str, category: str, priority: str, username: str) -> dict:
    """
    Creates a new ticket, processes it with AI, saves to DB, and logs knowledge gaps.
    """
    analysis = llm_engine.analyze_ticket(title, description, priority, category)
    normalized_query = normalize_ticket_text(title, description)
    suggested_kb_filename = analysis.get("suggested_kb_filename") or suggest_kb_filename(normalized_query)
    gap_group_key = None
    alert_result = None

    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tickets (
                title,
                description,
                category,
                priority,
                user_id,
                ai_resolution,
                confidence_score,
                resolution_status,
                retrieval_score,
                kb_context_found,
                normalized_query,
                suggested_kb_filename
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                description,
                category,
                priority,
                username,
                analysis["resolution_text"],
                analysis["confidence_score"],
                analysis["resolution_status"],
                analysis["retrieval_score"],
                int(bool(analysis["kb_context_found"])),
                normalized_query,
                suggested_kb_filename,
            ),
        )
        ticket_id = cursor.lastrowid

        if analysis["resolution_status"] in {"tentative", "unresolved"}:
            gap_group_key, alert_result = _upsert_knowledge_gap(
                cursor=cursor,
                ticket_id=ticket_id,
                category=category,
                normalized_query=normalized_query,
                confidence_score=analysis["confidence_score"],
                suggested_kb_filename=suggested_kb_filename,
            )
            cursor.execute(
                "UPDATE tickets SET gap_group_key = ? WHERE id = ?",
                (gap_group_key, ticket_id),
            )

        conn.commit()
    finally:
        conn.close()

    saved_ticket = get_ticket_by_id(ticket_id)
    saved_ticket["alert_status"] = alert_result["status"] if alert_result else None
    return saved_ticket

def submit_feedback(ticket_id, feedback_value, user_id):
    """ Stores one helpful/not_helpful response for a user's ticket."""
    if feedback_value not in {"helpful", "not_helpful"}:
        raise ValueError("Invalid feedback value. Must be 'helpful' or 'not_helpful'.")
    
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE tickets 
            SET feedback_value = ?,feedback_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ? AND feedback_value IS NULL
            """,
            (feedback_value,ticket_id,user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def get_all_tickets():
    """Returns all tickets from the database."""
    conn = database.get_db_connection()
    try:
        return pd.read_sql_query("SELECT * FROM tickets ORDER BY created_at DESC", conn)
    finally:
        conn.close()

def get_user_tickets(user_id):
    """Retrieves tickets for a specifie user."""
    conn = database.get_db_connection()
    try:
        query = "SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC"
        return pd.read_sql_query(query,conn,params=(user_id,))
    finally:
        conn.close()

def get_ticket_by_id(ticket_id):
    """Retrieves a single ticket by ID."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE id = ?",(ticket_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_admin_kpis():
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
        """
        SELECT
            COUNT(*) AS total_tickets,
            SUM(CASE WHEN resolution_status = 'resolved' THEN 1 ELSE 0 END) AS resolved_tickets,
            SUM(CASE WHEN resolution_status = 'unresolved' THEN 1 ELSE 0 END) AS unresolved_tickets,
            SUM(CASE WHEN resolution_status = 'tentative' THEN 1 ELSE 0 END) AS tentative_tickets,
            ROUND(AVG(confidence_score), 3) AS avg_confidence,
            SUM(CASE WHEN feedback_value = 'helpful' THEN 1 ELSE 0 END) AS helpful_count,
            SUM(CASE WHEN feedback_value = 'not_helpful' THEN 1 ELSE 0 END) AS not_helpful_count
        FROM tickets
        """
        )
        row =dict(cursor.fetchone())
        feedback_total  = (row["helpful_count"] or 0) +(row["not_helpful_count"] or 0)
        row["helpful_rate"] = round((row["helpful_count"] or 0)/ feedback_total,3) if feedback_total else 0.0
        return row
    finally:
        conn.close()

def get_top_questions(limit=10):
    conn = database.get_db_connection()
    try:
        return pd.read_sql_query(
            """
            SELECT normalized_query, category, COUNT(*) AS ticket_count, MAX(created_at) AS latest_seen
            FROM tickets
            GROUP BY normalized_query, category
            ORDER BY ticket_count DESC, latest_seen DESC
            LIMIT ?
            """,
            conn,
            params=(limit,)
        )
    finally:
        conn.close()

def get_ticket_trends():
    conn = database.get_db_connection()
    try:
        # Group by date of creation
        return pd.read_sql_query(
            """
            SELECT date(created_at) as date, COUNT(*) as ticket_count, AVG(confidence_score) as avg_confidence
            FROM tickets
            GROUP BY date(created_at)
            ORDER BY date(created_at) ASC
            """,
            conn
        )
    finally:
        conn.close()

def get_status_distribution():
    conn = database.get_db_connection()
    try:
        return pd.read_sql_query(
            """
            SELECT resolution_status, COUNT(*) as count
            FROM tickets
            GROUP BY resolution_status
            """,
            conn
        )
    finally:
        conn.close()

def initialize_system():
    """Initializes the database and ensures AI models are available."""
    database.init_db()
    llm_engine.check_model_availability()