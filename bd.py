# bd.py

import psycopg2
from config import DATABASE_URL

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_pg_db():
    """
    Створює таблицю players, якщо її ще немає.
    + гарантує наявність колонок user_name та first_name.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            # якщо таблиці ще нема — створюємо
            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    user_id    BIGINT PRIMARY KEY,
                    points     INTEGER NOT NULL DEFAULT 0,
                    user_name  TEXT,
                    first_name TEXT
                );
            """)

            # на випадок старої версії таблиці
            cur.execute("""
                ALTER TABLE players
                ADD COLUMN IF NOT EXISTS user_name  TEXT;
            """)
            cur.execute("""
                ALTER TABLE players
                ADD COLUMN IF NOT EXISTS first_name TEXT;
            """)
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


def ensure_user_pg(user_id: int, user_name: str | None = None, first_name: str | None = None):
    """
    Гарантує, що користувач є в players.
    Якщо є username / first_name — оновлює їх.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO players (user_id, points, user_name, first_name)
                VALUES (%s, 0, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET 
                    user_name  = COALESCE(EXCLUDED.user_name, players.user_name),
                    first_name = COALESCE(EXCLUDED.first_name, players.first_name);
                """,
                (user_id, user_name, first_name)
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


