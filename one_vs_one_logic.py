# one_vs_one_logic.py
import os
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не знайдено у змінних середовища")


def _get_conn():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode=os.getenv("PG_SSLMODE", "require")
    )


# ============================
#   ХЕЛПЕРИ
# ============================

CHOICE_BEATS = {
    "rock": "scissors",
    "scissors": "paper",
    "paper": "rock",
}


def _calc_winner(p1_choice: str | None, p2_choice: str | None) -> int | None:
    """
    Повертає:
    - 1  якщо виграв seat 1
    - 2  якщо виграв seat 2
    - None якщо нічия або ще немає обох ходів
    """
    if not p1_choice or not p2_choice:
        return None

    if p1_choice == p2_choice:
        return None

    if CHOICE_BEATS.get(p1_choice) == p2_choice:
        return 1
    if CHOICE_BEATS.get(p2_choice) == p1_choice:
        return 2

    return None


# ============================
#   JOIN: ЗАЙТИ В КІМНАТУ
# ============================

def join_one_vs_one(user_id: int, username: str | None):
    """
    Підсаджує гравця в існуючу "waiting" кімнату або створює нову.

    Повертає dict:
    {
      "room_id": int,
      "seat": 1|2,
      "status": "waiting"|"active",
      "players": [
        {"user_id": ..., "username": ..., "seat": 1, "total_points": 0},
        ...
      ]
    }
    """
    conn = _get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1) шукаємо кімнату, де < 2 гравців
            cur.execute(
                """
                SELECT r.id, r.status
                FROM one_vs_one_rooms r
                LEFT JOIN one_vs_one_players p ON p.room_id = r.id
                WHERE r.status IN ('waiting', 'active')
                GROUP BY r.id, r.status
                HAVING COUNT(p.id) < 2
                ORDER BY r.created_at
                LIMIT 1;
                """
            )
            row = cur.fetchone()

            if row:
                room_id = row["id"]
            else:
                # створюємо нову кімнату, де ти стаєш "host"
                cur.execute(
                    """
                    INSERT INTO one_vs_one_rooms (host_user_id, host_username)
                    VALUES (%s, %s)
                    RETURNING id;
                    """,
                    (user_id, username),
                )
                room_id = cur.fetchone()["id"]

            # 2) чи вже сидить цей user у кімнаті?
            cur.execute(
                """
                SELECT seat FROM one_vs_one_players
                WHERE room_id = %s AND user_id = %s;
                """,
                (room_id, user_id),
            )
            existing = cur.fetchone()
            if existing:
                seat = existing["seat"]
            else:
                # визначаємо вільний seat (1 або 2)
                cur.execute(
                    """
                    SELECT seat FROM one_vs_one_players
                    WHERE room_id = %s
                    ORDER BY seat;
                    """,
                    (room_id,),
                )
                taken = [r["seat"] for r in cur.fetchall()]
                if 1 not in taken:
                    seat = 1
                elif 2 not in taken:
                    seat = 2
                else:
                    raise RuntimeError("Кімната вже заповнена")

                cur.execute(
                    """
                    INSERT INTO one_vs_one_players (room_id, user_id, username, seat)
                    VALUES (%s, %s, %s, %s)
                    RETURNING seat;
                    """,
                    (room_id, user_id, username, seat),
                )
                seat = cur.fetchone()["seat"]

            # 3) якщо вже двоє – робимо кімнату active
            cur.execute(
                """
                SELECT COUNT(*) AS c
                FROM one_vs_one_players
                WHERE room_id = %s;
                """,
                (room_id,),
            )
            cnt = cur.fetchone()["c"]

            status = "waiting"
            if cnt >= 2:
                cur.execute(
                    """
                    UPDATE one_vs_one_rooms
                    SET status = 'active',
                        started_at = COALESCE(started_at, NOW())
                    WHERE id = %s
                    RETURNING status;
                    """,
                    (room_id,),
                )
                status = cur.fetchone()["status"]

            # 4) список гравців
            cur.execute(
                """
                SELECT user_id, username, seat, total_points
                FROM one_vs_one_players
                WHERE room_id = %s
                ORDER BY seat;
                """,
                (room_id,),
            )
            players = cur.fetchall()

            return {
                "room_id": room_id,
                "seat": seat,
                "status": status,
                "players": players,
            }

    finally:
        conn.close()


# ============================
#   MOVE: ЗРОБИТИ ХІД
# ============================

def make_move(
    room_id: int,
    user_id: int,
    round_index: int,
    game_index: int,
    choice: str,
):
    """
    Робить хід гравця, рахує результат, якщо обидва зробили хід.

    Повертає dict:
    {
      "room_id": ...,
      "round_index": ...,
      "game_index": ...,
      "status": "pending"|"waiting_opponent"|"finished",
      "winner_seat": 1|2|None,
      "my_seat": 1|2,
      "players": [...],     # як у join
      "turn": {
          "p1_choice": "..."/None,
          "p2_choice": "..."/None,
      }
    }
    """
    choice = choice.lower()
    if choice not in ("rock", "paper", "scissors"):
        raise ValueError("Невалідний choice")

    conn = _get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1) знаходимо seat гравця
            cur.execute(
                """
                SELECT seat FROM one_vs_one_players
                WHERE room_id = %s AND user_id = %s;
                """,
                (room_id, user_id),
            )
            p = cur.fetchone()
            if not p:
                raise RuntimeError("Гравець не в цій кімнаті")
            my_seat = p["seat"]

            # 2) дістаємо поточний turn з блокуванням
            cur.execute(
                """
                SELECT *
                FROM one_vs_one_turns
                WHERE room_id = %s AND round_index = %s AND game_index = %s
                FOR UPDATE;
                """,
                (room_id, round_index, game_index),
            )
            turn = cur.fetchone()

            if not turn:
                # створюємо новий turn
                if my_seat == 1:
                    cur.execute(
                        """
                        INSERT INTO one_vs_one_turns
                            (room_id, round_index, game_index, p1_choice, status)
                        VALUES (%s, %s, %s, %s, 'pending')
                        RETURNING *;
                        """,
                        (room_id, round_index, game_index, choice),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO one_vs_one_turns
                            (room_id, round_index, game_index, p2_choice, status)
                        VALUES (%s, %s, %s, %s, 'pending')
                        RETURNING *;
                        """,
                        (room_id, round_index, game_index, choice),
                    )
                turn = cur.fetchone()
            else:
                # оновлюємо вибір гравця, якщо ще не стоїть
                if turn["status"] == "finished":
                    # хід вже завершений – просто віддаємо поточний стан
                    pass
                else:
                    if my_seat == 1 and not turn["p1_choice"]:
                        cur.execute(
                            """
                            UPDATE one_vs_one_turns
                            SET p1_choice = %s
                            WHERE id = %s
                            RETURNING *;
                            """,
                            (choice, turn["id"]),
                        )
                        turn = cur.fetchone()
                    elif my_seat == 2 and not turn["p2_choice"]:
                        cur.execute(
                            """
                            UPDATE one_vs_one_turns
                            SET p2_choice = %s
                            WHERE id = %s
                            RETURNING *;
                            """,
                            (choice, turn["id"]),
                        )
                        turn = cur.fetchone()

            # 3) якщо обидва ходи вже є – рахуємо результат
            winner_seat = turn["winner_seat"]
            status = turn["status"]

            if status != "finished" and turn["p1_choice"] and turn["p2_choice"]:
                winner_seat = _calc_winner(turn["p1_choice"], turn["p2_choice"])

                # система балів: win=2, draw=1, lose=0
                if winner_seat is None:
                    # нічия – обом по 1
                    cur.execute(
                        """
                        UPDATE one_vs_one_players
                        SET total_points = total_points + 1,
                            rounds_draw = rounds_draw + 1
                        WHERE room_id = %s AND seat IN (1, 2);
                        """,
                        (room_id,),
                    )
                else:
                    winner = winner_seat
                    loser = 1 if winner_seat == 2 else 2

                    cur.execute(
                        """
                        UPDATE one_vs_one_players
                        SET total_points = total_points + 2,
                            rounds_won = rounds_won + 1
                        WHERE room_id = %s AND seat = %s;
                        """,
                        (room_id, winner),
                    )
                    cur.execute(
                        """
                        UPDATE one_vs_one_players
                        SET rounds_lost = rounds_lost + 1
                        WHERE room_id = %s AND seat = %s;
                        """,
                        (room_id, loser),
                    )

                # фіксуємо turn як завершений
                cur.execute(
                    """
                    UPDATE one_vs_one_turns
                    SET winner_seat = %s,
                        status = 'finished',
                        finished_at = NOW()
                    WHERE id = %s
                    RETURNING *;
                    """,
                    (winner_seat, turn["id"]),
                )
                turn = cur.fetchone()
                status = "finished"

            elif status != "finished":
                # є тільки один хід – чекаємо суперника
                status = "pending"

            # 4) дістаємо оновлених гравців
            cur.execute(
                """
                SELECT user_id, username, seat, total_points
                FROM one_vs_one_players
                WHERE room_id = %s
                ORDER BY seat;
                """,
                (room_id,),
            )
            players = cur.fetchall()

            return {
                "room_id": room_id,
                "round_index": round_index,
                "game_index": game_index,
                "status": status,
                "winner_seat": turn["winner_seat"],
                "my_seat": my_seat,
                "players": players,
                "turn": {
                    "p1_choice": turn["p1_choice"],
                    "p2_choice": turn["p2_choice"],
                },
            }

    finally:
        conn.close()


# ============================
#   STATE: СТАН КІМНАТИ
# ============================

def get_room_state(room_id: int, user_id: int | None = None):
    """
    Повертає повний стан кімнати (для періодичного опитування з фронта).

    {
      "room": {...},
      "me_seat": 1|2|None,
      "players": [...],
      "turns": [
           {round_index, game_index, p1_choice, p2_choice, winner_seat, status},
           ...
      ]
    }
    """
    conn = _get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            # кімната
            cur.execute(
                "SELECT * FROM one_vs_one_rooms WHERE id = %s;",
                (room_id,),
            )
            room = cur.fetchone()
            if not room:
                raise RuntimeError("Кімната не знайдена")

            # гравці
            cur.execute(
                """
                SELECT user_id, username, seat, total_points
                FROM one_vs_one_players
                WHERE room_id = %s
                ORDER BY seat;
                """,
                (room_id,),
            )
            players = cur.fetchall()

            # поточний раунд (поки один – current_round)
            current_round = room["current_round"]

            cur.execute(
                """
                SELECT room_id, round_index, game_index,
                       p1_choice, p2_choice, winner_seat, status
                FROM one_vs_one_turns
                WHERE room_id = %s AND round_index = %s
                ORDER BY game_index;
                """,
                (room_id, current_round),
            )
            turns = cur.fetchall()

            me_seat = None
            if user_id is not None:
                cur.execute(
                    """
                    SELECT seat
                    FROM one_vs_one_players
                    WHERE room_id = %s AND user_id = %s;
                    """,
                    (room_id, user_id),
                )
                row = cur.fetchone()
                if row:
                    me_seat = row["seat"]

            return {
                "room": room,
                "me_seat": me_seat,
                "players": players,
                "turns": turns,
            }

    finally:
        conn.close()
