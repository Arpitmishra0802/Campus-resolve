"""
Campus Resolve - Database Layer (models.py)
SQLite database configuration, tables schema, and query helper functions.
"""

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get("DATABASE_PATH", "campus_resolve.db")

@contextmanager
def get_db():
    """Context manager for SQLite database connection. Automatically commits and closes."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initializes SQLite tables and indexes."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # USERS table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student', 'management')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # COMPLAINTS table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT UNIQUE NOT NULL,
                student_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                location TEXT DEFAULT 'Campus Grounds',
                category TEXT NOT NULL,
                image TEXT,
                priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High', 'Critical')),
                status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Submitted', 'In Progress', 'Resolved', 'Closed')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)
        
        # COMPLAINT_UPDATES table (chronological audit log)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS complaint_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complaint_id INTEGER NOT NULL,
                management_id INTEGER,
                status TEXT NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (complaint_id) REFERENCES complaints (id) ON DELETE CASCADE,
                FOREIGN KEY (management_id) REFERENCES users (id) ON DELETE SET NULL
            );
        """)
        
        # Indexes for optimized triage and search
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_ticket ON complaints(ticket_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_student ON complaints(student_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_category ON complaints(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_priority ON complaints(priority);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_updates_complaint ON complaint_updates(complaint_id);")
        
        conn.commit()

# --- User Management Helpers ---

def create_user(name, email, password, role="student"):
    """Creates a new user with hashed password."""
    email_clean = email.strip().lower()
    pw_hash = generate_password_hash(password)
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (name.strip(), email_clean, pw_hash, role)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

def get_user_by_email(email):
    """Fetches user by email (case-insensitive)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip(),))
        return cursor.fetchone()

def get_user_by_id(user_id):
    """Fetches user by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()

# --- Complaint Generation & Queries ---

def generate_ticket_id():
    """Generates a unique, human-readable ticket ID like CR-2026-1042."""
    year = datetime.now().year
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) FROM complaints")
        max_id = cursor.fetchone()[0] or 1000
        next_number = max_id + 1
        return f"CR-{year}-{next_number:04d}"

def create_complaint(student_id, title, description, category, location=None, image=None, priority="Medium"):
    """Creates a complaint, generates unique ticket ID, and logs initial event."""
    ticket_id = generate_ticket_id()
    if not location or not location.strip():
        location = "Campus Grounds"
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO complaints (ticket_id, student_id, title, description, location, category, image, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Submitted')
        """, (ticket_id, student_id, title.strip(), description.strip(), location.strip(), category.strip(), image, priority))
        
        complaint_id = cursor.lastrowid
        
        # Log initial submission in timeline
        cursor.execute("""
            INSERT INTO complaint_updates (complaint_id, management_id, status, message)
            VALUES (?, NULL, 'Submitted', 'Grievance submitted by student. Awaiting initial triage.')
        """, (complaint_id,))
        
        conn.commit()
        return ticket_id

def get_complaint_by_ticket_id(ticket_id):
    """Retrieves full complaint information along with student details."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, u.name as student_name, u.email as student_email
            FROM complaints c
            JOIN users u ON c.student_id = u.id
            WHERE c.ticket_id = ?
        """, (ticket_id.strip(),))
        return cursor.fetchone()

def get_complaint_timeline(complaint_id):
    """Returns chronological audit trail / updates for a complaint."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cu.*, u.name as management_name, u.role as management_role
            FROM complaint_updates cu
            LEFT JOIN users u ON cu.management_id = u.id
            WHERE cu.complaint_id = ?
            ORDER BY cu.created_at ASC, cu.id ASC
        """, (complaint_id,))
        return cursor.fetchall()

def get_student_complaints(student_id, search=None, status=None, category=None):
    """Returns filtered complaints belonging to a specific student."""
    query = """
        SELECT c.*, u.name as student_name
        FROM complaints c
        JOIN users u ON c.student_id = u.id
        WHERE c.student_id = ?
    """
    params = [student_id]
    
    if search:
        query += " AND (c.ticket_id LIKE ? OR c.title LIKE ? OR c.description LIKE ? OR c.location LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s])
        
    if status and status != "All":
        query += " AND c.status = ?"
        params.append(status)
        
    if category and category != "All":
        query += " AND c.category = ?"
        params.append(category)
        
    query += " ORDER BY c.created_at DESC"
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

def get_all_complaints(search=None, status=None, category=None, priority=None):
    """Returns all complaints for management view with multi-criteria filtering."""
    query = """
        SELECT c.*, u.name as student_name, u.email as student_email,
               (SELECT message FROM complaint_updates WHERE complaint_id = c.id ORDER BY id DESC LIMIT 1) as latest_remark,
               (SELECT u2.name FROM complaint_updates cu2 JOIN users u2 ON cu2.management_id = u2.id WHERE cu2.complaint_id = c.id ORDER BY cu2.id DESC LIMIT 1) as latest_handler
        FROM complaints c
        JOIN users u ON c.student_id = u.id
        WHERE 1=1
    """
    params = []
    
    if search:
        query += " AND (c.ticket_id LIKE ? OR c.title LIKE ? OR c.description LIKE ? OR c.location LIKE ? OR u.name LIKE ? OR u.email LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s, s, s])
        
    if status and status != "All":
        query += " AND c.status = ?"
        params.append(status)
        
    if category and category != "All":
        query += " AND c.category = ?"
        params.append(category)
        
    if priority and priority != "All":
        query += " AND c.priority = ?"
        params.append(priority)
        
    query += " ORDER BY c.created_at DESC"
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

def get_complaint_counts(student_id=None):
    """Returns total, submitted, in_progress, resolved, and closed counts."""
    base_where = "WHERE student_id = ?" if student_id else ""
    params = [student_id] if student_id else []
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Submitted' THEN 1 ELSE 0 END) as submitted,
                SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
                SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved,
                SUM(CASE WHEN status = 'Closed' THEN 1 ELSE 0 END) as closed
            FROM complaints {base_where}
        """, params)
        row = cursor.fetchone()
        return {
            "total": row["total"] or 0,
            "submitted": row["submitted"] or 0,
            "in_progress": row["in_progress"] or 0,
            "resolved": row["resolved"] or 0,
            "closed": row["closed"] or 0
        }

def update_complaint_status_and_remarks(complaint_id, management_id, new_status, remarks=None, new_priority=None):
    """
    Updates status and/or priority of a complaint and appends an entry to the audit log.
    Ensures updates are atomic within a database transaction.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verify existence
        cursor.execute("SELECT status, priority FROM complaints WHERE id = ?", (complaint_id,))
        curr = cursor.fetchone()
        if not curr:
            return False
            
        old_status = curr["status"]
        old_priority = curr["priority"]
        
        # Prepare fields to update
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params = []
        
        if new_status and new_status in ['Submitted', 'In Progress', 'Resolved', 'Closed']:
            updates.append("status = ?")
            params.append(new_status)
        else:
            new_status = old_status
            
        if new_priority and new_priority in ['Low', 'Medium', 'High', 'Critical']:
            updates.append("priority = ?")
            params.append(new_priority)
        else:
            new_priority = old_priority
            
        params.append(complaint_id)
        cursor.execute(f"UPDATE complaints SET {', '.join(updates)} WHERE id = ?", params)
        
        # Determine log message
        log_message = remarks.strip() if remarks and remarks.strip() else ""
        if not log_message:
            changes = []
            if new_status != old_status:
                changes.append(f"Status changed from '{old_status}' to '{new_status}'")
            if new_priority != old_priority:
                changes.append(f"Priority changed from '{old_priority}' to '{new_priority}'")
            log_message = "; ".join(changes) if changes else f"Reviewed by management. Status remains {new_status}."
        elif new_status != old_status or new_priority != old_priority:
            prefix = []
            if new_status != old_status:
                prefix.append(f"Status: {new_status}")
            if new_priority != old_priority:
                prefix.append(f"Priority: {new_priority}")
            log_message = f"[{', '.join(prefix)}] {log_message}"
            
        cursor.execute("""
            INSERT INTO complaint_updates (complaint_id, management_id, status, message)
            VALUES (?, ?, ?, ?)
        """, (complaint_id, management_id, new_status, log_message))
        
        conn.commit()
        return True
