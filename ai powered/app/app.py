import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import auth_service
import ticket_service
import database

# Page Configuration
st.set_page_config(
    page_title="AI Ticket Resolution System",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Minimal Custom Styling (Only for custom HTML components)
st.markdown("""
    <style>
    /* Resolution Box */
    .resolution-box {
        background-color: #1e293b;
        color: white;
        padding: 1.5rem;
        border-left: 4px solid #10b981;
        border-radius: 8px;
        margin-top: 15px;
        border: 1px solid #334155;
    }
    
    /* Custom Badges */
    .status-badge {
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        color: white;
    }
    
    .status-resolved { background-color: #064e3b; }
    .status-tentative { background-color: #78350f; }
    .status-unresolved { background-color: #7f1d1d; }
    </style>
""", unsafe_allow_html=True)

# Session State Initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi! I'm the IT Support AI. Describe your problem and I'll search our company documentation to fix it instantly!"}]

# Initialize Database
@st.cache_resource
def init_app():
    database.init_db()
    auth_service.create_default_users()
    ticket_service.llm_engine.check_model_availability()

init_app()

def login():
    # Centered layout for login page
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("<h1 style='text-align: center; margin-bottom: 2rem;'>🎫 AI Support Portal</h1>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["🔒 Secure Login", "📝 Create Account"])
        
        with tab1:
            with st.form("login_form"):
                st.markdown("### Welcome Back")
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Enter System")
                
                if submitted:
                    user = auth_service.login_user(username, password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.username = user['username']
                        st.session_state.role = user['role']
                        st.success("Authentication successful! Loading dashboard...")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
        
        with tab2:
            with st.form("signup_form"):
                st.markdown("### New User Registration")
                new_user = st.text_input("Choose Username")
                new_pass = st.text_input("Create Password", type="password")
                confirm_pass = st.text_input("Confirm Password", type="password")
                role = st.selectbox("Role Request", ["user", "admin"])
                submitted = st.form_submit_button("Register Account")
                
                if submitted:
                    if new_pass != confirm_pass:
                        st.error("Passwords do not match!")
                    elif len(new_pass) < 6:
                        st.error("Security alert: Password must be at least 6 characters.")
                    else:
                        if auth_service.register_user(new_user, new_pass, role):
                            st.success("Profile created! You may now login.")
                        else:
                            st.error("That username is already taken.")

def user_dashboard():
    st.sidebar.title(f"👤 Welcome, {st.session_state.username}")
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()
    
    tab1, tab2 = st.tabs(["⚡ New Incident", "📂 My History"])
    
    with tab1:
        st.markdown("<h2>🚀 Lightning Fast IT Support</h2>", unsafe_allow_html=True)
        st.write("If the chat couldn't solve your issue, log a formal ticket here.")
        with st.form("ticket_form"):
            title = st.text_input("Issue Title", placeholder="e.g., Cannot access VPN")
            description = st.text_area("Detailed Description", placeholder="Please describe what happened...")
            attached_file = st.file_uploader("Attach a screenshot or text file (Optional)", type=["txt", "png", "jpg", "jpeg"])
            
            col1, col2 = st.columns(2)
            category = col1.selectbox("Category", ["Technical", "Access", "Hardware", "Billing", "General"])
            priority = col2.selectbox("Priority", ["Low", "Medium", "High", "Urgent"])
            
            submitted = st.form_submit_button("Submit & Get Resolution 🚀")
            
        if submitted:
            if not title or not description:
                st.warning("Please fill in both title and description.")
            else:
                if attached_file is not None:
                    if attached_file.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                        st.image(attached_file, caption="Attached Image")
                        description += f"\n\n--- Attached Image ({attached_file.name}) ---"
                        st.info(f"Attached image {attached_file.name} to the ticket context.")
                    else:
                        try:
                            file_contents = attached_file.getvalue().decode("utf-8")
                            description += f"\n\n--- Attached File ({attached_file.name}) ---\n{file_contents}"
                            st.info(f"Attached {attached_file.name} to the ticket context.")
                        except Exception as e:
                            st.error(f"Failed to read file: {e}")
                
                with st.spinner("AI is analyzing your issue..."):
                    ticket = ticket_service.submit_ticket(
                        title, description, category, priority, st.session_state.username
                    )
                    st.success(f"Ticket #{ticket['id']} submitted!")
                    
                    st.markdown("### 🤖 AI Suggested Resolution")
                    status_class = f"status-{ticket['resolution_status']}"
                    st.markdown(f"""
                        <div class="resolution-box">
                            <p><strong>Status:</strong> <span class="status-badge {status_class}">{ticket['resolution_status'].upper()}</span></p>
                            <p><strong>Confidence:</strong> {ticket['confidence_score']*100:.1f}%</p>
                            <hr style="border-top:1px solid #334155;"/>
                            {ticket['ai_resolution']}
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Feedback
                    st.info("Was this resolution helpful?")
                    f_col1, f_col2, _ = st.columns([1, 1, 4])
                    if f_col1.button("👍 Helpful"):
                        ticket_service.submit_feedback(ticket['id'], "helpful", st.session_state.username)
                        st.toast("Thank you for your feedback!")
                    if f_col2.button("👎 Not Helpful"):
                        ticket_service.submit_feedback(ticket['id'], "not_helpful", st.session_state.username)
                        st.toast("We'll work on improving this.")

    with tab2:
        st.header("Your Tickets")
        tickets_df = ticket_service.get_user_tickets(st.session_state.username)
        
        if tickets_df.empty:
            st.info("You haven't submitted any tickets yet.")
        else:
            for _, row in tickets_df.iterrows():
                status_class = f"status-{row['resolution_status']}"
                with st.expander(f"#{row['id']} - {row['title']} ({row['created_at']})"):
                    st.markdown(f"**Category:** {row['category']} | **Priority:** {row['priority']}")
                    st.markdown(f"**Description:**\n{row['description']}")
                    st.markdown(f"""
                        <div class="resolution-box">
                            <p><strong>AI Resolution:</strong> <span class="status-badge {status_class}">{row['resolution_status'].upper()}</span></p>
                            {row['ai_resolution']}
                        </div>
                    """, unsafe_allow_html=True)

def admin_dashboard():
    st.sidebar.title(f"👑 Admin: {st.session_state.username}")
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()
    
    st.markdown("<h1>🚀 Admin Analytics Dashboard</h1>", unsafe_allow_html=True)
    
    # KPIs
    kpis = ticket_service.get_admin_kpis()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Tickets", kpis['total_tickets'], "Active")
    col2.metric("Resolved Rate", f"{(kpis['resolved_tickets']/kpis['total_tickets']*100 if kpis['total_tickets'] else 0):.1f}%", "Target > 80%")
    col3.metric("Avg Confidence", f"{kpis['avg_confidence']*100:.1f}%", "AI accuracy")
    col4.metric("Helpful Rate", f"{kpis['helpful_rate']*100:.1f}%", "User Feedback")
    
    tab1, tab2, tab3 = st.tabs(["📈 Trends", "🔍 Knowledge Gaps", "📋 All Tickets"])
    
    with tab1:
        st.subheader("Dashboard Analytics")
        
        # Row 1: Trends and Status Distribution
        col_t1, col_t2 = st.columns(2)
        
        with col_t1:
            st.markdown("### Ticket Volume Trends")
            trends_df = ticket_service.get_ticket_trends()
            if not trends_df.empty:
                fig = px.line(trends_df, x='date', y='ticket_count', title="Tickets Over Time", markers=True)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("No trend data available.")
                
        with col_t2:
            st.markdown("### Resolution Status")
            status_df = ticket_service.get_status_distribution()
            if not status_df.empty:
                fig = px.pie(status_df, names='resolution_status', values='count', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("No status data available.")
        
        st.markdown("---")
        st.subheader("Top Question Categories")
        top_q = ticket_service.get_top_questions()
        if not top_q.empty:
            category_counts = top_q.groupby('category')['ticket_count'].sum().reset_index()
            fig = px.bar(category_counts, x='category', y='ticket_count', title="Tickets by Category", color='category')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No data yet.")

    with tab2:
        st.subheader("Detected Knowledge Gaps")
        st.info("These are recurring issues where the AI has low confidence. Consider adding these to your documentation.")
        
        conn = database.get_db_connection()
        gaps_df = pd.read_sql_query("SELECT * FROM knowledge_gap_events ORDER BY occurrence_count DESC", conn)
        conn.close()
        
        if gaps_df.empty:
            st.write("No knowledge gaps detected yet.")
        else:
            st.dataframe(gaps_df[['display_query', 'category', 'occurrence_count', 'avg_confidence_score', 'suggested_kb_filename']], use_container_width=True)

    with tab3:
        st.subheader("System-wide Ticket Queue")
        all_tickets = ticket_service.get_all_tickets()
        st.dataframe(all_tickets, use_container_width=True)

# Main Application Entry Point
if not st.session_state.authenticated:
    login()
else:
    if st.session_state.role == "admin":
        admin_dashboard()
    else:
        user_dashboard()
