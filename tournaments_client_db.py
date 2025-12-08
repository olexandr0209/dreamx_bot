# tournaments_client_db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не знайдено у змінних середовища")

def _get_conn():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode=os.getenv("PG_SSLMODE", "require")
    )

def list_upcoming(limit: int = 20):
    """
    Повертає список найближчих турнірів.
    ⚠️ Назви колонок підженеш під свою таблицю tournaments.
    """
    sql = """
        SELECT
            id,
            title,
            starts_at,
            host_username,
            players_total,
            players_left,
            status,
            description
        FROM tournaments
        WHERE status IN ('scheduled', 'active')
        ORDER BY starts_at ASC
        LIMIT %s
    """
    with _get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (limit,))
        return cur.fetchall()

def get_tournament_by_id(tournament_id: int):
    sql = """
        SELECT
            id,
            title,
            starts_at,
            host_username,
            players_total,
            players_left,
            status,
            description
        FROM tournaments
        WHERE id = %s
        LIMIT 1
    """
    with _get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (tournament_id,))
        row = cur.fetchone()
        return row
