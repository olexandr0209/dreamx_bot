# tournaments_game_db.py
import os
import random
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")


def _get_conn():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode=os.getenv("PG_SSLMODE", "require")
    )


# ------------------------
#   Допоміжна логіка
# ------------------------

CHOICES = ("rock", "paper", "scissors")


def _beats(a: str, b: str) -> bool:
    return (
        (a == "rock" and b == "scissors")
        or (a == "scissors" and b == "paper")
        or (a == "paper" and b == "rock")
    )


def _compute_result(m1: str, m2: str) -> str:
    """
    Повертає:
      - 'p1_win'
      - 'p2_win'
      - 'draw'
    """
    if m1 not in CHOICES or m2 not in CHOICES:
        raise ValueError("invalid_move")

    if m1 == m2:
        return "draw"
    if _beats(m1, m2):
        return "p1_win"
    return "p2_win"


# ------------------------
#   Гравці в турнірі
# ------------------------

def register_player(tournament_id: int, player_id: int) -> dict:
    """
    Реєструє гравця в турнірі (якщо ще не зареєстрований).
    Повертає row з tournament_players (id, status).
    """
    conn = _get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, status
                FROM tournament_players
                WHERE tournament_id = %s AND player_id = %s
                """,
                (tournament_id, player_id),
            )
            row = cur.fetchone()
            if row:
                # Вже є в турнірі
                return row

            cur.execute(
                """
                INSERT INTO tournament_players (tournament_id, player_id, status)
                VALUES (%s, %s, 'active')
                RETURNING id, status
                """,
                (tournament_id, player_id),
            )
            return cur.fetchone()
    finally:
        conn.close()


def _get_tournament_player_id(cur, tournament_id: int, player_id: int) -> int:
    """
    Внутрішня функція: повертає id з tournament_players для цього турніру.
    Викликається всередині транзакції (cur).
    """
    cur.execute(
        """
        SELECT id
        FROM tournament_players
        WHERE tournament_id = %s AND player_id = %s
        """,
        (tournament_id, player_id),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError("not_registered")
    return row["id"]


# ------------------------
#   Створення раунду + груп
# ------------------------

def create_group_round_from_active(tournament_id: int, round_number: int) -> int:
    """
    Створює раунд (round_number) і групи з усіх ACTIVE-гравців турніру.
    Формує таблиці:
      - tournament_rounds
      - tournament_groups
      - tournament_group_players
      - matches
    Повертає round_id.
    """
    conn = _get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Чи вже є такий раунд?
            cur.execute(
                """
                SELECT id
                FROM tournament_rounds
                WHERE tournament_id = %s AND round_number = %s
                """,
                (tournament_id, round_number),
            )
            existing = cur.fetchone()
            if existing:
                return existing["id"]

            # 1) створюємо раунд
            cur.execute(
                """
                INSERT INTO tournament_rounds (tournament_id, round_number, type, status)
                VALUES (%s, %s, 'group', 'running')
                RETURNING id
                """,
                (tournament_id, round_number),
            )
            round_id = cur.fetchone()["id"]

            # 2) беремо всіх active-гравців турніру
            cur.execute(
                """
                SELECT id
                FROM tournament_players
                WHERE tournament_id = %s AND status = 'active'
                ORDER BY id
                """,
                (tournament_id,),
            )
            rows = cur.fetchall()
            tp_ids = [r["id"] for r in rows]

            if len(tp_ids) < 2:
                raise ValueError("not_enough_players")

            random.shuffle(tp_ids)

            n = len(tp_ids)
            base_groups = n // 4
            rem = n % 4

            group_sizes = []

            if base_groups == 0:
                # мало гравців — одна група
                group_sizes = [n]
            else:
                if rem == 0:
                    group_sizes = [4] * base_groups
                elif rem == 1:
                    # приклад: 9 -> 2 групи по 4 + 1 гравець => 1 група по 5
                    if base_groups >= 1:
                        group_sizes = [4] * (base_groups - 1) + [5]
                    else:
                        group_sizes = [n]
                elif rem == 2:
                    # приклад: 10 -> 2 групи по 4 + 2 => 2 групи по 5
                    if base_groups >= 2:
                        group_sizes = [4] * (base_groups - 2) + [5, 5]
                    else:
                        group_sizes = [n]
                elif rem == 3:
                    # приклад: 11 -> 2 групи по 4 + 3
                    group_sizes = [4] * base_groups + [3]

            # 3) створюємо групи + гравців у групах + матчі
            index = 1
            pos = 0

            for size in group_sizes:
                cur.execute(
                    """
                    INSERT INTO tournament_groups (tournament_id, round_id, group_index, status, size)
                    VALUES (%s, %s, %s, 'running', %s)
                    RETURNING id
                    """,
                    (tournament_id, round_id, index, size),
                )
                group_id = cur.fetchone()["id"]
                index += 1

                group_tp_ids = tp_ids[pos : pos + size]
                pos += size

                # додаємо гравців у групу
                for tp_id in group_tp_ids:
                    cur.execute(
                        """
                        INSERT INTO tournament_group_players (
                            tournament_id, round_id, group_id, tournament_player_id, score, is_qualified
                        )
                        VALUES (%s, %s, %s, %s, 0, FALSE)
                        """,
                        (tournament_id, round_id, group_id, tp_id),
                    )

                # створюємо матчі (кожен з кожним)
                for i in range(len(group_tp_ids)):
                    for j in range(i + 1, len(group_tp_ids)):
                        p1 = group_tp_ids[i]
                        p2 = group_tp_ids[j]
                        cur.execute(
                            """
                            INSERT INTO matches (
                                tournament_id, round_id, group_id,
                                player1_id, player2_id, status
                            )
                            VALUES (%s, %s, %s, %s, %s, 'pending')
                            """,
                            (tournament_id, round_id, group_id, p1, p2),
                        )

            return round_id
    finally:
        conn.close()


# ------------------------
#   Отримати наступний матч гравця
# ------------------------

def get_next_match_for_player(tournament_id: int, player_id: int) -> dict | None:
    """
    Повертає найближчий матч для гравця в цьому турнірі,
    де статус != finished. Якщо матчів немає — None.
    """
    conn = _get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            tp_id = _get_tournament_player_id(cur, tournament_id, player_id)

            cur.execute(
                """
                SELECT *
                FROM matches
                WHERE tournament_id = %s
                  AND (player1_id = %s OR player2_id = %s)
                  AND status <> 'finished'
                ORDER BY id
                LIMIT 1
                """,
                (tournament_id, tp_id, tp_id),
            )
            match = cur.fetchone()
            return match
    finally:
        conn.close()


# ------------------------
#   Зробити хід у матчі
# ------------------------

def submit_move(tournament_id: int, match_id: int, player_id: int, move: str) -> dict:
    """
    Записує хід гравця в матчі.
    Якщо після цього обидва зробили хід — рахує результат,
    оновлює очки в tournament_group_players і повертає результат.
    """
    move = move.lower()
    if move not in CHOICES:
        raise ValueError("invalid_move")

    conn = _get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            tp_id = _get_tournament_player_id(cur, tournament_id, player_id)

            # читаємо матч
            cur.execute(
                """
                SELECT *
                FROM matches
                WHERE id = %s AND tournament_id = %s
                FOR UPDATE
                """,
                (match_id, tournament_id),
            )
            match = cur.fetchone()
            if not match:
                raise ValueError("match_not_found")

            if match["status"] == "finished":
                return {
                    "status": "already_finished",
                    "result": match["result"],
                    "player1_move": match["player1_move"],
                    "player2_move": match["player2_move"],
                }

            # визначаємо, який це гравець
            if tp_id == match["player1_id"]:
                col = "player1_move"
            elif tp_id == match["player2_id"]:
                col = "player2_move"
            else:
                raise ValueError("not_in_match")

            # якщо хід уже був — нічого не робимо
            if match[col] is not None:
                # повернемо поточний стан
                return {
                    "status": match["status"],
                    "player1_move": match["player1_move"],
                    "player2_move": match["player2_move"],
                    "result": match["result"],
                }

            # оновлюємо хід
            cur.execute(
                f"UPDATE matches SET {col} = %s WHERE id = %s",
                (move, match_id),
            )

            # перечитуємо матч
            cur.execute(
                """
                SELECT *
                FROM matches
                WHERE id = %s
                """,
                (match_id,),
            )
            match = cur.fetchone()
            m1 = match["player1_move"]
            m2 = match["player2_move"]

            if not m1 or not m2:
                # чекаємо другого гравця
                cur.execute(
                    """
                    UPDATE matches
                    SET status = 'waiting_for_moves'
                    WHERE id = %s
                    """,
                    (match_id,),
                )
                return {
                    "status": "waiting_for_opponent",
                    "player1_move": m1,
                    "player2_move": m2,
                }

            # є обидва ходи -> рахуємо результат
            result = _compute_result(m1, m2)

            if result == "draw":
                p1_delta = 1
                p2_delta = 1
            elif result == "p1_win":
                p1_delta = 3
                p2_delta = 0
            else:  # p2_win
                p1_delta = 0
                p2_delta = 3

            # оновлюємо матч
            cur.execute(
                """
                UPDATE matches
                SET result = %s,
                    status = 'finished',
                    finished_at = NOW()
                WHERE id = %s
                """,
                (result, match_id),
            )

            # оновлюємо очки в групі
            cur.execute(
                """
                UPDATE tournament_group_players
                SET score = score + %s
                WHERE tournament_id = %s
                  AND round_id = %s
                  AND group_id = %s
                  AND tournament_player_id = %s
                """,
                (
                    p1_delta,
                    match["tournament_id"],
                    match["round_id"],
                    match["group_id"],
                    match["player1_id"],
                ),
            )
            cur.execute(
                """
                UPDATE tournament_group_players
                SET score = score + %s
                WHERE tournament_id = %s
                  AND round_id = %s
                  AND group_id = %s
                  AND tournament_player_id = %s
                """,
                (
                    p2_delta,
                    match["tournament_id"],
                    match["round_id"],
                    match["group_id"],
                    match["player2_id"],
                ),
            )

            return {
                "status": "finished",
                "result": result,
                "player1_move": m1,
                "player2_move": m2,
                "player1_delta": p1_delta,
                "player2_delta": p2_delta,
            }
    finally:
        conn.close()
