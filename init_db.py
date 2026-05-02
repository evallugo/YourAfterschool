"""Run once to create the PostgreSQL database tables and default admin account."""
import os
import psycopg2
from werkzeug.security import generate_password_hash

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/yas')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
SCHEMA       = os.path.join(os.path.dirname(__file__), 'schema.sql')


def init():
    conn = psycopg2.connect(DATABASE_URL)
    cur  = conn.cursor()

    with open(SCHEMA) as f:
        cur.execute(f.read())

    cur.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (%s, %s, %s, %s)",
            ['admin', generate_password_hash('admin123'), 'Administrator', 'admin']
        )
        print("Created default admin — username: admin, password: admin123")
        print("CHANGE THIS PASSWORD after first login via Admin > Users.")

    conn.commit()
    cur.close()
    conn.close()
    print("Database initialised.")


if __name__ == '__main__':
    init()
