# bd.py

import psycopg2
from config import DATABASE_URL

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_pg_db():
    """
    Створює таблицю players, якщо її ще немає.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    user_id BIGINT PRIMARY KEY,
                    points INTEGER NOT NULL DEFAULT 0
                );
            """)
        print("PostgreSQL: таблиця players готова")
    finally:
        conn.close()


def get_points_pg(user_id: int) -> int:
    """
    Гарантує, що гравець існує.
    Якщо немає рядка з user_id — створює його з 0 балів.
    Потім повертає поточні points.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            # Створюємо, якщо нема
            cur.execute(
                """
                INSERT INTO players (user_id, points)
                VALUES (%s, 0)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,)
            )

            # Читаємо
            cur.execute(
                "SELECT points FROM players WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            return row[0] if row else 0
    finally:
        conn.close()


def add_points_pg(user_id: int, amount: int):
    """
    Додає amount балів. Якщо гравця нема — створює.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO players (user_id, points)
                VALUES (%s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET points = players.points + EXCLUDED.points
                """,
                (user_id, amount)
            )
    finally:
        conn.close()


def ensure_user_pg(user_id: int):
    """
    Гарантує, що користувач є в players.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO players (user_id, points)
                VALUES (%s, 0)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,)
            )
    finally:
        conn.close()


def add_points_and_return(user_id: int, delta: int) -> int:
    """
    Додає delta поінтів і повертає новий баланс.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE players
                SET points = points + %s
                WHERE user_id = %s
                RETURNING points
                """,
                (delta, user_id)
            )
            row = cur.fetchone()

            if not row:
                cur.execute(
                    """
                    INSERT INTO players (user_id, points)
                    VALUES (%s, %s)
                    RETURNING points
                    """,
                    (user_id, delta)
                )
                row = cur.fetchone()

            return row[0]
    finally:
        conn.close()
