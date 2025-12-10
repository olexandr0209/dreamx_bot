# one_vs_one_db.py
import os
import psycopg2

from config import DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не знайдено у змінних середовища")


def _get_conn():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode=os.getenv("PG_SSLMODE", "require")
    )


def init_one_vs_one_tables():
    conn = _get_conn()
    try:
        with conn, conn.cursor() as cur:
            # 1) Кімнати
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS one_vs_one_rooms (
                    id              BIGSERIAL PRIMARY KEY,
                    host_user_id    BIGINT,
                    host_username   TEXT,
                    status          TEXT NOT NULL DEFAULT 'waiting',
                    current_round   INTEGER NOT NULL DEFAULT 1,
                    total_rounds    INTEGER NOT NULL DEFAULT 1,
                    games_per_round INTEGER NOT NULL DEFAULT 3,
                    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
                    started_at      TIMESTAMP,
                    finished_at     TIMESTAMP
                );
                """
            )

            # 2) Гравці
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS one_vs_one_players (
                    id              BIGSERIAL PRIMARY KEY,
                    room_id         BIGINT NOT NULL REFERENCES one_vs_one_rooms(id) ON DELETE CASCADE,
                    user_id         BIGINT NOT NULL,
                    username        TEXT,
                    seat            INTEGER NOT NULL,
                    joined_at       TIMESTAMP NOT NULL DEFAULT NOW(),
                    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
                    total_points    INTEGER NOT NULL DEFAULT 0,
                    rounds_won      INTEGER NOT NULL DEFAULT 0,
                    rounds_lost     INTEGER NOT NULL DEFAULT 0,
                    rounds_draw     INTEGER NOT NULL DEFAULT 0,
                    last_heartbeat  TIMESTAMP,
                    CONSTRAINT one_vs_one_players_unique_user_in_room
                        UNIQUE (room_id, user_id),
                    CONSTRAINT one_vs_one_players_unique_seat_in_room
                        UNIQUE (room_id, seat),
                    CONSTRAINT one_vs_one_players_seat_chk
                        CHECK (seat IN (1, 2))
                );
                """
            )

            # 3) Ходи (turns)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS one_vs_one_turns (
                    id              BIGSERIAL PRIMARY KEY,
                    room_id         BIGINT NOT NULL REFERENCES one_vs_one_rooms(id) ON DELETE CASCADE,
                    round_index     INTEGER NOT NULL,
                    game_index      INTEGER NOT NULL,
                    p1_choice       TEXT,
                    p2_choice       TEXT,
                    winner_seat     INTEGER,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
                    finished_at     TIMESTAMP,
                    CONSTRAINT one_vs_one_turns_chk_winner
                        CHECK (winner_seat IS NULL OR winner_seat IN (1, 2)),
                    CONSTRAINT one_vs_one_turns_unique_game
                        UNIQUE (room_id, round_index, game_index)
                );
                """
            )

    finally:
        conn.close()
