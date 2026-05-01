"""Run once to create the database and default admin account."""
import sqlite3
import os
from werkzeug.security import generate_password_hash

DATABASE = os.path.join(os.path.dirname(__file__), 'yas.db')
SCHEMA   = os.path.join(os.path.dirname(__file__), 'schema.sql')

def init():
    db = sqlite3.connect(DATABASE)
    with open(SCHEMA) as f:
        db.executescript(f.read())

    # Create default admin if none exists
    existing = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
            ['admin', generate_password_hash('admin123'), 'Administrator', 'admin']
        )
        print("Created default admin — username: admin, password: admin123")
        print("CHANGE THIS PASSWORD after first login via Admin > Users.")

    db.commit()
    db.close()
    print(f"Database initialized at {DATABASE}")

if __name__ == '__main__':
    init()
