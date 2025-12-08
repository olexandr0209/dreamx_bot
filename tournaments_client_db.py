# tournaments_client_db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL   # як у bd.py / giveaway_db_from_admin.py


if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")


def _get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode=os.getenv("PG_SSLMODE", "require"))


def get_upcoming_tournaments(limit: int = 20):
    """
    Повертає заплановані турніри для WebApp.
    """
    sql = """
        SELECT
            id,
            title,
            prize,
            start_dt,
            status
        FROM tournaments
        WHERE status = 'scheduled'
        ORDER BY start_dt ASC
        LIMIT %s
    """
    conn = _get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
            # перейменуємо start_dt -> start_at для фронта
            for r in rows:
                r["start_at"] = r.pop("start_dt")
            return rows
    finally:
        conn.close()


# 🔥 alias, який використовує main.py
def list_upcoming(limit: int = 20):
    """
    Те саме, що get_upcoming_tournaments, просто інша назва для main.py.
    """
    return get_upcoming_tournaments(limit)


def get_tournament_by_id(t_id: int):
    """
    Отримати один турнір по id (для /api/get_tournament).
    """
    sql = """
        SELECT
            id,
            title,
            prize,
            start_dt,
            status
        FROM tournaments
        WHERE id = %s
        LIMIT 1
    """
    conn = _get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (t_id,))
            row = cur.fetchone()
            if not row:
                return None
            row["start_at"] = row.pop("start_dt")
            return row
    finally:
        conn.close()
