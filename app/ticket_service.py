import database
import llm_engine
import rag_engine
import pandas as pd

def submit_ticket(title, description, category, priority, user_id):
    """
    Creates a new ticket, processes it with AI, and saves to DB.
    """
    # 1. AI Processing
    # We pass category context to AI but let it refine or focus on resolution
    _, resolution = llm_engine.analyze_ticket(title, description, priority, category)
    
    # 2. Save to DB
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tickets (title, description, category, priority, user_id, ai_resolution)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, description, category, priority, user_id, resolution))
        conn.commit()
    finally:
        conn.close()
    
    return True

def get_all_tickets():
    """Retrieves all tickets (Admin view)."""
    conn = database.get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM tickets ORDER BY created_at DESC", conn)
        return df
    finally:
        conn.close()

def get_user_tickets(user_id):
    """Retrieves tickets for a specific user."""
    conn = database.get_db_connection()
    try:
        # Parameterized query for safety
        query = "SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC"
        df = pd.read_sql_query(query, conn, params=(user_id,))
        return df
    finally:
        conn.close()

def get_ticket_by_id(ticket_id):
    """Retrieves a single ticket by ID."""
    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def initialize_system():
    """Ensures DB is ready and Model is pulled. Documents must be ingested manually."""
    database.init_db()
    llm_engine.check_model_availability()
    # rag_engine.ingest_documents() # Decoupled for manual execution