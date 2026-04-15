import os
import sys

# Ensure we can import from local app dir
sys.path.append(os.path.join(os.getcwd(), 'app'))
import database
import config

def fix_database():
    print(f"Checking database at {database.DB_NAME}...")
    
    if not os.path.exists(database.DB_NAME):
        print("Database does not exist. Initializing fresh database...")
        database.init_db()
        print("Done.")
        return

    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        print("Ensuring all required columns exist in 'tickets' table...")
        database._ensure_ticket_columns(cursor)
        
        # Additional checks can be added here
        # e.g., checking for 'users' table or 'knowledge_gap_events'
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("Creating missing 'users' table...")
            cursor.execute('''
                CREATE TABLE users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL
                );
            ''')

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_gap_events'")
        if not cursor.fetchone():
            print("Creating missing 'knowledge_gap_events' table...")
            cursor.execute('''
                CREATE TABLE knowledge_gap_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gap_group_key TEXT NOT NULL UNIQUE,
                    normalized_query TEXT NOT NULL,
                    display_query TEXT NOT NULL,
                    suggested_kb_filename TEXT,
                    category TEXT,
                    occurrence_count INTEGER DEFAULT 0,
                    latest_ticket_id INTEGER,
                    latest_confidence_score REAL DEFAULT 0.0,
                    avg_confidence_score REAL DEFAULT 0.0,
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_alert_count INTEGER DEFAULT 0,
                    last_alert_status TEXT,
                    last_alert_message TEXT,
                    last_alert_at TIMESTAMP,
                    FOREIGN KEY(latest_ticket_id) REFERENCES tickets(id)
                );
            ''')

        conn.commit()
        print("Database check and fix complete.")
    except Exception as e:
        print(f"Error fixing database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_database()
