"""
Campus Resolve - Database Initialization and Seed Script (seed_data.py)
Initializes SQLite schema and ensures the management administrator account exists.
Optionally seeds demo complaints when run with the --demo flag.
"""

import sys
import os
import shutil
from models import init_db, create_user, get_user_by_email, get_db, DB_PATH

def init_system(with_demo=False):
    print(f"Initializing database at: {DB_PATH}")
    init_db()

    # Ensure uploads directory exists
    uploads_dir = os.path.join("static", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    # Ensure management admin exists
    admin = get_user_by_email("admin@campus.edu")
    if not admin:
        create_user("Estate & Facilities Officer", "admin@campus.edu", "Admin@123", role="management")
        print("Created default management account: admin@campus.edu")
    else:
        print("Management account already exists.")

    if not with_demo:
        print("Clean initialization complete. No demo complaints inserted.")
        return

    # Seed demo complaints only if explicitly requested
    print("Seeding optional demo grievances...")
    with get_db() as conn:
        cursor = conn.cursor()
        student1_id = create_user("Alex Morgan", "alex@college.edu", "Student@123", role="student") or 1
        
        cursor.execute("""
            INSERT OR IGNORE INTO complaints (ticket_id, student_id, title, description, location, category, priority, status)
            VALUES ('CR-2026-1001', ?, 'Sample Wi-Fi Outage', 'Demo issue for testing.', 'CS Lab 2', 'Internet', 'High', 'Submitted')
        """, (student1_id,))
        conn.commit()
    print("Demo data seeded.")

if __name__ == "__main__":
    include_demo = "--demo" in sys.argv
    init_system(with_demo=include_demo)
