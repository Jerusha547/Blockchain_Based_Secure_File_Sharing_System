"""
Database initialization and connection management.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "secure_share.db")

def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Create all tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cur = conn.cursor()

    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    UNIQUE NOT NULL,
            email    TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # OTP table for forgot-password
    cur.execute("""
        CREATE TABLE IF NOT EXISTS otp_store (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL,
            otp        TEXT    NOT NULL,
            expires_at DATETIME NOT NULL
        )
    """)

    # Files table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_username  TEXT    NOT NULL,
            original_name   TEXT    NOT NULL,
            stored_name     TEXT    NOT NULL,
            file_path       TEXT    NOT NULL,
            blockchain_hash TEXT    NOT NULL,
            aes_key_hex     TEXT    NOT NULL,
            uploaded_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_username) REFERENCES users(username)
        )
    """)

    # File permissions table (access control)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS file_permissions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id        INTEGER NOT NULL,
            granted_to     TEXT    NOT NULL,
            granted_by     TEXT    NOT NULL,
            granted_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files(id),
            UNIQUE(file_id, granted_to)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized.")
