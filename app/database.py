import os
import sqlite3

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "attendance.db")

def get_db_path():
    """Return the configured SQLite database path from environment variable or default."""
    return os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)

def get_db_connection(db_path=None):
    """Establish and return a SQLite database connection with row access by column name."""
    path = db_path or get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path=None):
    """Initialize database tables for students and attendance."""
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_no TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Present', 'Absent')),
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE(student_id, date)
            );
        """)
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {get_db_path()}")
