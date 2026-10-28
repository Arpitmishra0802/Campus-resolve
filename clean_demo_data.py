"""
Script to remove all demo grievances, demo updates, demo files, and demo student accounts,
while preserving the admin account and any real student accounts registered by the user.
"""

import os
import sqlite3

DB_PATH = "campus_resolve.db"
UPLOADS_DIR = os.path.join("static", "uploads")

DEMO_EMAILS = [
    "alex@college.edu",
    "priyah@college.edu",
    "david@college.edu",
    "student@campus.edu"
]

def clean_data():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # 1. Remove all complaint updates
    cursor.execute("DELETE FROM complaint_updates;")
    print("Cleared complaint_updates table.")

    # 2. Remove all complaints
    cursor.execute("DELETE FROM complaints;")
    print("Cleared complaints table.")

    # 3. Reset sqlite sequence for complaints & updates
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('complaints', 'complaint_updates');")
    print("Reset ticket counter sequence.")

    # 4. Remove demo student users
    cursor.execute(
        f"DELETE FROM users WHERE email IN ({','.join(['?']*len(DEMO_EMAILS))});",
        DEMO_EMAILS
    )
    print(f"Removed demo accounts: {', '.join(DEMO_EMAILS)}")

    conn.commit()

    # Show remaining users
    cursor.execute("SELECT id, name, email, role FROM users;")
    remaining = cursor.fetchall()
    print("\nRemaining Accounts:")
    for u in remaining:
        print(f" - [{u[3]}] {u[1]} ({u[2]})")

    conn.close()

    # 5. Clean files in static/uploads
    if os.path.exists(UPLOADS_DIR):
        for f in os.listdir(UPLOADS_DIR):
            file_path = os.path.join(UPLOADS_DIR, f)
            if os.path.isfile(file_path):
                os.remove(file_path)
        print("\nEmptied static/uploads directory.")

    print("\nDemo data cleanup completed successfully!")

if __name__ == "__main__":
    clean_data()

