# db.py

import os
import psycopg2
from dotenv import load_dotenv
import sqlite3
from contextlib import closing
from config import DATABASE_URL

load_dotenv()

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
    """
    Гарантує, що гравець існує.
    Якщо немає рядка з user_id — створює його з 0 балів.
    Потім повертає поточні points.
    """
    conn = connect_db()
    cur = conn.cursor()

    # 1️⃣ Створюємо юзера, якщо його ще нема
    cur.execute(
        """
        INSERT INTO players (user_id, points)
        VALUES (%s, 0)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id,)
    )

    # 2️⃣ Читаємо поточні бали
    cur.execute("SELECT points FROM players WHERE user_id = %s", (user_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    return row[0] if row else 0


def add_points_pg(user_id: int, amount: int):
    conn = connect_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO players (user_id, points)
        VALUES (%s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET points = players.points + EXCLUDED.points
        """,
        (user_id, amount)
    )

    cur.close()
    conn.close()


def ensure_user_pg(user_id: int):
    """
    Гарантує, що користувач існує в таблиці players.
    Якщо його нема — створює з points = 0.
    Якщо є — нічого не робить.
    """
    conn = connect_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO players (user_id, points)
        VALUES (%s, 0)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id,)
    )

    cur.close()
    conn.close()


# bd.py
import os
import psycopg2

def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")


def get_or_create_user_points(user_id: int) -> int:
    """
    Повертає кількість поінтів користувача.
    Якщо користувача немає в базі — створює його з 0 поінтів і повертає 0.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            # 1. Пробуємо знайти користувача
            cur.execute(
                "SELECT points FROM users WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            if row:
                return row[0]

            # 2. Якщо немає — створюємо з 0
            cur.execute(
                "INSERT INTO users (user_id, points) VALUES (%s, %s) RETURNING points",
                (user_id, 0)
            )
            new_row = cur.fetchone()
            return new_row[0]
    finally:
        conn.close()


def add_points_and_return(user_id: int, delta: int) -> int:
    """
    Додає delta поінтів (може бути відʼємним) користувачу.
    Якщо користувача ще немає — створює його і одразу додає йому delta.
    Повертає новий баланс.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            # Спочатку пробуємо оновити
            cur.execute(
                """
                UPDATE users
                SET points = points + %s
                WHERE user_id = %s
                RETURNING points
                """,
                (delta, user_id)
            )
            row = cur.fetchone()

            if not row:
                # Якщо рядків не оновилось — користувача не існує
                cur.execute(
                    """
                    INSERT INTO users (user_id, points)
                    VALUES (%s, %s)
                    RETURNING points
                    """,
                    (user_id, delta)
                )
                row = cur.fetchone()

            conn.commit()
            return row[0]
    finally:
        conn.close()
