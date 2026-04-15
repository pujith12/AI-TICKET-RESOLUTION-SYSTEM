import sys
import os

# Ensure app imports work properly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pandas as pd

import auth_service
import ticket_service
import database

# Initialize core DB and default users before starting API
database.init_db()
auth_service.create_default_users()

app = FastAPI(title="AI Knowledge Engine API", version="2.0.0")

# Enable CORS for the future frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELS ---
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "user"

class TicketSubmission(BaseModel):
    title: str
    description: str
    category: str
    priority: str
    username: str

class FeedbackSubmission(BaseModel):
    ticket_id: int
    feedback_type: str
    username: str

# --- AUTH ENDPOINTS ---
@app.post("/api/auth/login")
def login(request: LoginRequest):
    user = auth_service.login_user(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"message": "Login successful", "user": {"username": user["username"], "role": user["role"]}}

@app.post("/api/auth/register")
def register(request: RegisterRequest):
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    success = auth_service.register_user(request.username, request.password, request.role)
    if not success:
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"message": "User registered successfully"}

# --- TICKET ENDPOINTS ---
@app.post("/api/tickets")
def create_ticket(ticket: TicketSubmission):
    try:
        # Calls the LLM and RAG engine inside
        result = ticket_service.submit_ticket(
            title=ticket.title,
            description=ticket.description,
            category=ticket.category,
            priority=ticket.priority,
            username=ticket.username
        )
        # Convert dictionary to prevent SQLite row issues
        return {"message": "Ticket generated", "data": dict(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tickets/user/{username}")
def get_user_tickets(username: str):
    df = ticket_service.get_user_tickets(username)
    # Convert DataFrame to list of dicts for JSON
    return df.to_dict(orient="records")

@app.post("/api/tickets/feedback")
def submit_feedback(feedback: FeedbackSubmission):
    ticket_service.submit_feedback(feedback.ticket_id, feedback.feedback_type, feedback.username)
    return {"message": "Feedback recorded"}

# --- ADMIN ENDPOINTS ---
@app.get("/api/admin/metrics")
def get_admin_metrics():
    metrics = ticket_service.get_admin_kpis()
    # Handle NaN values if any
    for k, v in metrics.items():
         if pd.isna(v): metrics[k] = 0
    return metrics

@app.get("/api/admin/top-categories")
def get_top_categories():
    df = ticket_service.get_top_questions()
    return df.to_dict(orient="records")

@app.get("/api/admin/knowledge-gaps")
def get_knowledge_gaps():
    conn = database.get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM knowledge_gap_events ORDER BY occurrence_count DESC", conn)
        return df.to_dict(orient="records")
    except Exception as e:
        return []
    finally:
        conn.close()

@app.get("/api/admin/tickets")
def get_all_tickets():
    df = ticket_service.get_all_tickets()
    return df.to_dict(orient="records")
