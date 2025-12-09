# tournaments_client_db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL   # той самий, що в bd.py / giveaway_db_from_admin.py


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


def get_tournament_by_id(tid: int):
    """
    Один турнір по id.
    """
    sql = """
        SELECT
            id,
            title,
            prize,
            start_dt,
            status,
            host_username
        FROM tournaments
        WHERE id = %s
    """
    conn = _get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (tid,))
            row = cur.fetchone()
            if row:
                row["start_at"] = row.pop("start_dt")
            return row
    finally:
        conn.close()
