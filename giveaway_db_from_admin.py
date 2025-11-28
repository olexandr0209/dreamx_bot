# admin_db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")  # той самий, що в основному боті

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не знайдено у змінних середовища")


def _get_conn():
    # просте підключення, без пулу — для початку достатньо
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def create_giveaway(
    title: str,
    prize: str,
    prize_count: int,
    description: str,
    gtype: str,
    start_dt,
    end_dt,
    extra_info: str | None,
    status: str = "scheduled",
) -> int:
    """
    Створює розіграш у таблиці giveaways і повертає id.
    """
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO giveaways
                        (title, prize, prize_count, description,
                         gtype, start_at, end_at, extra_info, status)
                    VALUES
                        (%s,    %s,    %s,          %s,
                         %s,    %s,      %s,     %s,         %s)
                    RETURNING id;
                    """,
                    (
                        title,
                        prize,
                        prize_count,
                        description,
                        gtype,
                        start_dt,
                        end_dt,
                        extra_info,
                        status,
                    ),
                )
                gid = cur.fetchone()[0]
        return gid
    finally:
        conn.close()


def create_promo_giveaway(title, prize, prize_count, description,
                          start_dt, end_dt, channel_count, status):
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO promo_giveaways
        (title, prize, prize_count, description, start_at, end_at, channel_count, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """, (title, prize, prize_count, description, start_dt, end_dt, channel_count, status))

    promo_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return promo_id


def add_promo_channel(promo_id, order_index, name, description, link):
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO promo_giveaway_channels
        (promo_id, order_index, name, description, link)
        VALUES (%s, %s, %s, %s, %s);
    """, (promo_id, order_index, name, description, link))

    conn.commit()
    cur.close()
    conn.close()

def create_announcement(
    title: str,
    message: str,
    extra_info: str | None,
    start_dt,
    end_dt,
    status: str = "scheduled",
) -> int:
    """
    Створює оголошення в таблиці announcements і повертає id.
    """
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO announcements
                        (title, message, extra_info, start_at, end_at, status)
                    VALUES
                        (%s,    %s,      %s,        %s,      %s,    %s)
                    RETURNING id;
                    """,
                    (title, message, extra_info, start_dt, end_dt, status),
                )
                ann_id = cur.fetchone()[0]
        return ann_id
    finally:
        conn.close()


def add_announcement_link(
    ann_id: int,
    order_index: int,
    title: str,
    description: str | None,
    url: str,
) -> None:
    """
    Додає одне посилання до оголошення в таблицю announcement_links.
    """
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO announcement_links
                        (ann_id, order_index, title, description, url)
                    VALUES
                        (%s,     %s,          %s,    %s,          %s);
                    """,
                    (ann_id, order_index, title, description, url),
                )
    finally:
        conn.close()

def get_announcements_for_admin(period: str) -> List[Dict]:
    """
    Повертає список оголошень для адміна за періодом.
    period: "today" | "this_week" | "last_2_weeks"
    Всі фільтри йдуть по даті start_at (коли оголошення стартує).
    """

    if period == "today":
        where = "DATE(start_at) = CURRENT_DATE"
    elif period == "this_week":
        where = (
            "DATE(start_at) BETWEEN "
            "date_trunc('week', CURRENT_DATE)::date "
            "AND (date_trunc('week', CURRENT_DATE) + interval '6 days')::date"
        )
    elif period == "last_2_weeks":
        where = "DATE(start_at) >= (CURRENT_DATE - interval '14 days')"
    else:
        raise ValueError("Unknown period")

    sql = f"""
        SELECT id, title, message, extra_info, start_at, end_at
        FROM announcements
        WHERE {where}
        ORDER BY start_at ASC;
    """

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    finally:
        conn.close()

    results: List[Dict] = []
    for r in rows:
        results.append(
            {
                "id": r[0],
                "title": r[1],
                "message": r[2],
                "extra_info": r[3],
                "start_at": r[4],
                "end_at": r[5],
            }
        )
    return results


def delete_announcement(ann_id: int) -> bool:
    """
    Видаляє оголошення (і всі його посилання).
    Повертає True, якщо щось було видалено.
    """
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # спочатку видаляємо посилання
                cur.execute(
                    "DELETE FROM announcement_links WHERE ann_id = %s",
                    (ann_id,)
                )
                # потім саме оголошення
                cur.execute(
                    "DELETE FROM announcements WHERE id = %s",
                    (ann_id,)
                )
                return cur.rowcount > 0
    finally:
        conn.close()


def get_giveaways_for_admin(kind: str, period: str) -> List[Dict]:
    """
    kind: "normal" або "promo"
    period: "today" | "this_week" | "last_2_weeks"
    """

    if kind == "normal":
        table = "giveaways"
    elif kind == "promo":
        table = "promo_giveaways"
    else:
        raise ValueError("Unknown kind")

    if period == "today":
        where = "DATE(end_at) = CURRENT_DATE"
    elif period == "this_week":
        # тиждень з понеділка по неділю
        where = (
            "DATE(end_at) BETWEEN "
            "date_trunc('week', CURRENT_DATE)::date "
            "AND (date_trunc('week', CURRENT_DATE) + interval '6 days')::date"
        )
    elif period == "last_2_weeks":
        # за датою СТАРТУ (як дата створення) за останні 14 днів
        where = "DATE(start_at) >= (CURRENT_DATE - interval '14 days')"
    else:
        raise ValueError("Unknown period")

    sql = f"""
        SELECT id, title, prize, prize_count, description, start_at, end_at
        FROM {table}
        WHERE {where}
        ORDER BY end_at ASC;
    """

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    finally:
        conn.close()

    results: List[Dict] = []
    for r in rows:
        results.append(
            {
                "id": r[0],
                "title": r[1],
                "prize": r[2],
                "prize_count": r[3],
                "description": r[4],
                "start_at": r[5],
                "end_at": r[6],
            }
        )
    return results

def delete_giveaway(kind: str, giveaway_id: int) -> bool:
    """
    Видаляє розіграш по id.
    kind: "normal" -> таблиця giveaways
          "promo"  -> таблиця promo_giveaways
    Повертає True, якщо хоч один рядок був видалений.
    """
    if kind == "normal":
        table = "giveaways"
    elif kind == "promo":
        table = "promo_giveaways"
    else:
        raise ValueError("Unknown kind")

    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {table} WHERE id = %s",
                    (giveaway_id,)
                )
                return cur.rowcount > 0
    finally:
        conn.close()


# ======== Отримати активні функціі ================


def get_active_giveaways() -> list[dict]:
    """
    Активні звичайні розіграші:
    start_at <= NOW < end_at
    """
    sql = """
        SELECT id, title, prize, prize_count, description,
               gtype, extra_info, start_at, end_at
        FROM giveaways
        WHERE start_at <= NOW()
          AND end_at   > NOW()
        ORDER BY end_at ASC;
    """

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_active_promo_giveaways() -> list[dict]:
    """
    Активні рекламні розіграші з каналами.
    """
    sql_main = """
        SELECT id, title, prize, prize_count, description,
               start_at, end_at, channel_count
        FROM promo_giveaways
        WHERE start_at <= NOW()
          AND end_at   > NOW()
        ORDER BY end_at ASC;
    """

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql_main)
            promos = [dict(r) for r in cur.fetchall()]

            # добираємо канали для кожного promo
            for p in promos:
                cur.execute(
                    """
                    SELECT order_index, name, description, link
                    FROM promo_giveaway_channels
                    WHERE promo_id = %s
                    ORDER BY order_index ASC;
                    """,
                    (p["id"],)
                )
                ch_rows = cur.fetchall()
                p["channels"] = [dict(ch) for ch in ch_rows]

        return promos
    finally:
        conn.close()


def get_active_announcements() -> list[dict]:
    """
    Активні оголошення з посиланнями.
    """
    sql_main = """
        SELECT id, title, message, extra_info, start_at, end_at
        FROM announcements
        WHERE start_at <= NOW()
          AND end_at   > NOW()
        ORDER BY start_at ASC;
    """

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql_main)
            anns = [dict(r) for r in cur.fetchall()]

            for a in anns:
                cur.execute(
                    """
                    SELECT order_index, title, description, url
                    FROM announcement_links
                    WHERE ann_id = %s
                    ORDER BY order_index ASC;
                    """,
                    (a["id"],)
                )
                links = cur.fetchall()
                a["links"] = [dict(l) for l in links]

        return anns
    finally:
        conn.close()


def get_active_cards() -> list[dict]:
    """
    Єдиний список всіх активних карточок для фронта.
    Об'єднує:
    - звичайні розіграші (giveaways)  -> kind = "normal"
    - рекламні розіграші (promo_giveaways) -> kind = "promo"
    - оголошення (announcements) -> kind = "announcement"
    """
    cards: list[dict] = []

    # 1) Звичайні розіграші
    for g in get_active_giveaways():
        item = dict(g)
        item["kind"] = "normal"
        cards.append(item)

    # 2) Рекламні розіграші
    for p in get_active_promo_giveaways():
        item = dict(p)
        item["kind"] = "promo"
        cards.append(item)

    # 3) Оголошення
    for a in get_active_announcements():
        item = dict(a)
        item["kind"] = "announcement"
        cards.append(item)

    # Можна посортувати за start_at (якщо є), інакше по end_at
    def sort_key(x: dict):
        return x.get("start_at") or x.get("end_at") or datetime.max

    cards.sort(key=sort_key)

    return cards





def add_giveaway_player(giveaway_id: int, user_id: int, username_snapshot: str | None, points_in_giveaway: int = 1):
    """
    Додає участь користувача в розіграші.
    points_in_giveaway – завжди 1 при вході по кнопці.
    """
    conn = _get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO giveaway_players (giveaway_id, user_id, username_snapshot, points_in_giveaway)
                VALUES (%s, %s, %s, %s);
                """,
                (giveaway_id, user_id, username_snapshot, points_in_giveaway)
            )
    finally:
        conn.close()




