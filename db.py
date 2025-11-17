# db.py

import os
import psycopg2
from dotenv import load_dotenv
import sqlite3
from contextlib import closing
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

DB_NAME = "players.db"


def init_db():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS players (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                points INTEGER DEFAULT 0
            );
        """)
        conn.commit()


def get_or_create_player(user):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT points FROM players WHERE telegram_id = ?",
            (user.id,)
        )
        row = cur.fetchone()

        if row:
            return row[0]  # повертаємо наявні бали

        cur.execute("""
            INSERT INTO players (telegram_id, username, first_name, last_name, points)
            VALUES (?, ?, ?, ?, 0)
        """, (user.id, user.username, user.first_name, user.last_name))
        conn.commit()

        return 0


def get_points(telegram_id: int) -> int:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT points FROM players WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = cur.fetchone()
        return row[0] if row else 0


def add_points(telegram_id: int, amount: int):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE players
            SET points = points + ?
            WHERE telegram_id = ?
        """, (amount, telegram_id))
        conn.commit()

def connect_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn

def init_pg_db():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id BIGINT PRIMARY KEY,
            points INTEGER DEFAULT 0
        );
    """)

    cur.close()
    conn.close()
    print("PostgreSQL таблиця готова")

def get_or_create_pg(user_id: int) -> int:
    conn = connect_db()
    cur = conn.cursor()

    # Чи існує гравець?
    cur.execute("SELECT points FROM players WHERE user_id = %s", (user_id,))
    row = cur.fetchone()

    if row:
        cur.close()
        conn.close()
        return row[0]  # повертаємо бали

    # Якщо немає — створюємо
    cur.execute(
        "INSERT INTO players (user_id, points) VALUES (%s, 0)",
        (user_id,)
    )

    cur.close()
    conn.close()
    return 0

def get_points_pg(user_id: int) -> int:
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT points FROM players WHERE user_id = %s", (user_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    return row[0] if row else 0

def add_points_pg(user_id: int, amount: int):
    conn = connect_db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE players SET points = points + %s WHERE user_id = %s",
        (amount, user_id)
    )

    cur.close()
    conn.close()
