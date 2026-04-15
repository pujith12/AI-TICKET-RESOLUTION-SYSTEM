import html
import re

import altair as alt
import auth_service
import streamlit as st
import ticket_service


st.set_page_config(
    page_title="AI Support Gen",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)


@st.cache_resource
def init_app():
    ticket_service.initialize_system()
    auth_service.create_default_users()


init_app()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #e2e8f0;
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(37, 99, 235, 0.18), transparent 35%),
            radial-gradient(circle at top right, rgba(14, 165, 233, 0.16), transparent 30%),
            #0f1116;
    }

    .block-container {
        max-width: 1200px;
        padding-top: 2.5rem;
    }

    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    div[data-baseweb="select"] > div {
        background-color: #1e293b;
        color: #f8fafc;
        border: 1px solid #334155;
        border-radius: 8px;
    }

    div[data-testid="stFormSubmitButton"] > button,
    div[data-testid="stButton"] > button {
        border-radius: 8px;
        font-weight: 600;
    }

    .ticket-card {
        background-color: rgba(15, 23, 42, 0.88);
        border: 1px solid #334155;
        border-radius: 14px;
        padding: 1.25rem;
        margin-top: 1rem;
    }

    .metric-card {
        background: rgba(15, 23, 42, 0.88);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 0.9rem 1rem;
    }

    .chip {
        display: inline-block;
        padding: 0.2rem 0.65rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        margin-right: 0.4rem;
    }
</style>
""", unsafe_allow_html=True)


if "user" not in st.session_state:
    st.session_state["user"] = None
if "latest_submitted_ticket_id" not in st.session_state:
    st.session_state["latest_submitted_ticket_id"] = None


def auth_page():
    st.title("Welcome to AI Support")
    st.markdown("Your intelligent technical resolution partner.")

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        with st.form("login_form"):
            st.subheader("Sign In")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Access Account")

            if submit:
                if username and password:
                    user = auth_service.login_user(username, password)
                    if user:
                        st.session_state["user"] = user
                        st.success(f"Welcome back, {user['username']}!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
                else:
                    st.warning("Please enter both username and password.")

    with tab2:
        with st.form("signup_form"):
            st.subheader("Create Account")
            new_user = st.text_input("Choose Username")
            new_pass = st.text_input("Choose Password", type="password")
            confirm_pass = st.text_input("Confirm Password", type="password")
            submit_signup = st.form_submit_button("Register")

            if submit_signup:
                if new_user and new_pass and confirm_pass:
                    if new_pass != confirm_pass:
                        st.error("Passwords do not match.")
                    elif auth_service.register_user(new_user, new_pass, role="user"):
                        st.success("Account created. Please switch to Login.")
                    else:
                        st.error("Username already exists.")
                else:
                    st.warning("All fields are required.")


def confidence_label(score):
    if score >= 0.75:
        return "High confidence", "#22c55e"
    if score >= 0.45:
        return "Tentative", "#f59e0b"
    return "Low confidence", "#ef4444"


def normalize_resolution_markdown(text):
    if not text:
        return ""

    cleaned_text = re.sub(
        r"<div[^>]*>\s*AI Resolution\s*</div>",
        "",
        str(text),
        flags=re.IGNORECASE,
    ).strip()
    if len(cleaned_text) >= 2 and cleaned_text[0] == cleaned_text[-1] and cleaned_text[0] in {'"', "'"}:
        cleaned_text = cleaned_text[1:-1].strip()

    normalized_lines = []
    for line in cleaned_text.splitlines():
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]

        if stripped.startswith(("• ", "â€¢ ")):
            normalized_lines.append(f"{indent}- {stripped[2:].lstrip()}")
            continue
        if re.match(r"^\d+\)\s+", stripped):
            normalized_lines.append(f"{indent}{re.sub(r'^(\d+)\)\s+', r'\\1. ', stripped)}")
            continue

        normalized_lines.append(line)

    return "\n".join(normalized_lines).strip()


def compact_topic_label(label, unique_hint="", max_len=30):
    text = str(label or "").strip()
    hint = str(unique_hint or "").strip()
    if len(text) <= max_len:
        return text

    suffix = f" [{hint[:4]}]" if hint else ""
    head_len = max(8, max_len - len(suffix) - 3)
    return f"{text[:head_len]}...{suffix}"


def render_feedback_controls(ticket, user_id, render_context="default"):
    if ticket.get("feedback_value"):
        st.caption(f"Feedback recorded: `{ticket['feedback_value']}`")
        return

    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "👍 Helpful",
            key=f"helpful_{ticket['id']}_{render_context}",
            width="stretch",
        ):
            if ticket_service.submit_feedback(ticket["id"], "helpful", user_id):
                st.rerun()
    with col2:
        if st.button(
            "👎 Not helpful",
            key=f"not_helpful_{ticket['id']}_{render_context}",
            width="stretch",
        ):
            if ticket_service.submit_feedback(ticket["id"], "not_helpful", user_id):
                st.rerun()


def render_ticket_card(ticket, user_id=None, show_feedback=False, render_context="default"):
    label, label_color = confidence_label(ticket.get("confidence_score") or 0.0)
    category_color = "#38bdf8" if ticket["category"] in ["Network", "Security", "Hardware"] else "#94a3b8"
    priority_color = "#ef4444" if ticket["priority"] in ["High", "Critical"] else "#22c55e"
    status = ticket.get("resolution_status", "unresolved")
    resolution_md = normalize_resolution_markdown(ticket.get("ai_resolution", ""))
    safe_title = html.escape(ticket["title"])
    safe_desc = html.escape(ticket["description"])
    warning = ""
    if status == "tentative":
        warning = "<p style='color:#fbbf24; margin-top:0.75rem;'>Low confidence: review this suggestion before treating it as final guidance.</p>"
    elif status == "unresolved":
        warning = "<p style='color:#f87171; margin-top:0.75rem;'>The AI could not resolve this confidently. This ticket is tracked as a knowledge gap.</p>"

    st.markdown(
        f"""
        <div class="ticket-card">
            <div style="display:flex; justify-content:space-between; gap:1rem; align-items:flex-start;">
                <div>
                    <div style="font-size:1.1rem; font-weight:700; color:#f8fafc;">{safe_title}</div>
                    <div style="color:#94a3b8; font-size:0.85rem;">INC-{ticket['id']:04d} • {ticket['created_at'][:16]}</div>
                </div>
                <div>
                    <span class="chip" style="background:{category_color}; color:black;">{ticket['category']}</span>
                    <span class="chip" style="background:{priority_color}; color:white;">{ticket['priority']}</span>
                </div>
            </div>
            <p style="margin-top:0.9rem; color:#cbd5e1;">{safe_desc}</p>
            <div style="margin-top:0.75rem;">
                <span class="chip" style="background:{label_color}; color:black;">{label}</span>
                <span class="chip" style="background:#1d4ed8; color:white;">Score {ticket.get('confidence_score', 0.0):.2f}</span>
                <span class="chip" style="background:#334155; color:#f8fafc;">Status {status}</span>
            </div>
            {warning}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("**AI Resolution**")
    st.markdown(resolution_md or "_No AI resolution generated._")

    extra = []
    if ticket.get("suggested_kb_filename"):
        extra.append(f"Suggested KB file: `{ticket['suggested_kb_filename']}`")
    extra.append(f"Retrieval score: `{ticket.get('retrieval_score', 0.0):.2f}`")
    extra.append(f"KB context found: `{bool(ticket.get('kb_context_found'))}`")
    st.caption(" | ".join(extra))

    if show_feedback and user_id:
        render_feedback_controls(ticket, user_id, render_context=render_context)


def render_admin_dashboard():
    st.markdown("### Admin Analytics")
    kpis = ticket_service.get_admin_kpis()
    top_questions = ticket_service.get_top_questions()
    confidence_by_category = ticket_service.get_confidence_by_category()
    gap_groups = ticket_service.get_knowledge_gap_groups()
    heatmap = ticket_service.get_knowledge_gap_heatmap()
    alerts = ticket_service.get_recent_alerts()
    feedback = ticket_service.get_feedback_rollup()

    metric_cols = st.columns(5)
    metric_cols[0].metric("Total tickets", int(kpis["total_tickets"] or 0))
    metric_cols[1].metric("AI resolved", int(kpis["resolved_tickets"] or 0))
    metric_cols[2].metric("Tentative", int(kpis["tentative_tickets"] or 0))
    metric_cols[3].metric("Unresolved", int(kpis["unresolved_tickets"] or 0))
    metric_cols[4].metric("Helpful rate", f"{(kpis['helpful_rate'] or 0) * 100:.0f}%")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Most Frequently Asked Questions")
        if top_questions.empty:
            st.info("No ticket analytics yet.")
        else:
            st.dataframe(top_questions, width="stretch", hide_index=True)

        st.markdown("#### Average Confidence by Category")
        if confidence_by_category.empty:
            st.info("No confidence data yet.")
        else:
            st.bar_chart(
                confidence_by_category.set_index("category")["avg_confidence_score"],
                width="stretch",
            )
            st.dataframe(confidence_by_category, width="stretch", hide_index=True)

        st.markdown("#### Feedback Rollup")
        if feedback.empty:
            st.info("No feedback yet.")
        else:
            st.dataframe(feedback, width="stretch", hide_index=True)

    with right:
        st.markdown("#### Knowledge Gaps")
        if gap_groups.empty:
            st.info("No repeated low-confidence questions yet.")
        else:
            st.dataframe(gap_groups, width="stretch", hide_index=True)

        st.markdown("#### Knowledge Gap Heatmap")
        if heatmap.empty:
            st.info("No tentative or unresolved topics yet.")
        else:
            heatmap_data = heatmap.copy()
            heatmap_data["topic"] = heatmap_data.apply(
                lambda row: compact_topic_label(
                    row["topic_label"],
                    row.get("gap_group_key", ""),
                    max_len=30,
                ),
                axis=1,
            )
            topic_order = (
                heatmap_data.groupby("topic")
                .agg(
                    min_confidence=("avg_confidence_score", "min"),
                    total_tickets=("ticket_count", "sum"),
                )
                .sort_values(["min_confidence", "total_tickets"], ascending=[True, False])
                .index.tolist()
            )
            category_order = (
                heatmap_data.groupby("category")
                .agg(
                    min_confidence=("avg_confidence_score", "min"),
                    total_tickets=("ticket_count", "sum"),
                )
                .sort_values(["min_confidence", "total_tickets"], ascending=[True, False])
                .index.tolist()
            )
            chart_height = max(280, 42 * len(topic_order))

            heatmap_chart = alt.Chart(heatmap_data).mark_rect(
                stroke="#0f172a",
                strokeWidth=1,
            ).encode(
                x=alt.X(
                    "category:N",
                    sort=category_order,
                    title="Category",
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y(
                    "topic:N",
                    sort=topic_order,
                    title=None,
                    axis=alt.Axis(labelLimit=190, labelPadding=10),
                ),
                color=alt.Color(
                    "avg_confidence_score:Q",
                    title="Avg confidence",
                    scale=alt.Scale(domain=[0, 1], scheme="redyellowgreen"),
                ),
                tooltip=[
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("topic_label:N", title="Topic"),
                    alt.Tooltip("avg_confidence_score:Q", title="Avg confidence", format=".3f"),
                    alt.Tooltip("ticket_count:Q", title="Tickets"),
                    alt.Tooltip("last_seen_at:N", title="Last seen"),
                ],
            ).properties(height=chart_height)

            heatmap_labels = alt.Chart(heatmap_data).mark_text(fontSize=11).encode(
                x=alt.X("category:N", sort=category_order),
                y=alt.Y("topic:N", sort=topic_order),
                text=alt.Text("avg_confidence_score:Q", format=".2f"),
                color=alt.condition(
                    "datum.avg_confidence_score < 0.55",
                    alt.value("white"),
                    alt.value("black"),
                ),
            )

            combined_heatmap = (heatmap_chart + heatmap_labels).configure_axis(
                grid=False
            ).configure_view(
                strokeWidth=0
            )

            st.altair_chart(combined_heatmap, use_container_width=True)
            st.caption(
                "Red cells are weakest confidence. Each value is average confidence for repeated tentative/unresolved topics."
            )
            st.dataframe(
                heatmap_data[["category", "topic_label", "avg_confidence_score", "ticket_count", "last_seen_at"]],
                width="stretch",
                hide_index=True,
                column_config={
                    "topic_label": "topic",
                    "avg_confidence_score": st.column_config.NumberColumn(format="%.3f"),
                    "ticket_count": "tickets",
                    "last_seen_at": "last_seen_at",
                },
            )

        st.markdown("#### Recent Slack Alerts")
        if alerts.empty:
            st.info("No alert history yet.")
        else:
            st.dataframe(alerts, width="stretch", hide_index=True)


if not st.session_state["user"]:
    auth_page()
else:
    main_app_user = st.session_state["user"]
    is_admin = main_app_user.get("role") == "admin" 

    c1, c2 = st.columns([6, 1]) # 7 parts -> 6 part  1 part
    with c1:
        st.title("IT Operations")
        st.caption(f"Logged in as {main_app_user['username']} ({main_app_user['role']})")
    with c2:
        if st.button("Logout", type="secondary", width="stretch"):
            st.session_state["user"] = None
            st.rerun()

    tab_labels = ["New Incident", "My History"]
    if is_admin:
        tab_labels.append("Admin Dashboard")

    tabs = st.tabs(tab_labels)
    tab_submit = tabs[0]
    tab_history = tabs[1]
    tab_admin = tabs[2] if is_admin else None

    with tab_submit:
        st.markdown("### Describe your issue")
        st.markdown("The AI will retrieve KB context, propose a resolution, and log weak spots in the knowledge base.")

        with st.form("ticket_form"):
            c_a, c_b = st.columns(2)
            with c_a:
                cat = st.selectbox("Category", ["Hardware", "Software", "Network", "Account", "Security", "Other"])
            with c_b:
                prio = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"])

            title = st.text_input("Issue Title", placeholder="e.g. Cannot connect to VPN")
            desc = st.text_area(
                "Detailed Description",
                placeholder="Provide error messages, steps tried, and system details.",
                height=150,
            )

            submitted = st.form_submit_button("Analyze & Resolve")

            if submitted:
                if title and desc:
                    with st.spinner("Analyzing knowledge base and generating resolution..."):
                        saved_ticket = ticket_service.submit_ticket(
                            title,
                            desc,
                            cat,
                            prio,
                            main_app_user["username"],
                        )
                        st.session_state["latest_submitted_ticket_id"] = saved_ticket["id"]
                else:
                    st.warning("Please provide both title and description.")

        latest_ticket_id = st.session_state.get("latest_submitted_ticket_id")
        latest_ticket = (
            ticket_service.get_ticket_by_id(latest_ticket_id)
            if latest_ticket_id
            else None
        )
        if latest_ticket and latest_ticket.get("user_id") == main_app_user["username"]:
            st.success("Analysis complete.")
            render_ticket_card(
                latest_ticket,
                user_id=main_app_user["username"],
                show_feedback=True,
                render_context="latest_submission",
            )

    with tab_history:
        st.markdown("### Your Past Incidents")
        df_hist = ticket_service.get_user_tickets(main_app_user["username"])

        if df_hist.empty:
            st.info("No tickets found in history.")
        else:
            for _, row in df_hist.iterrows():
                with st.expander(f"{row['created_at'][:16]} | {row['title']} ({row['priority']})"):
                    render_ticket_card(
                        row.to_dict(),
                        user_id=main_app_user["username"],
                        show_feedback=True,
                        render_context=f"history_{row['id']}",
                    )

    if is_admin and tab_admin:
        with tab_admin:
            render_admin_dashboard()
