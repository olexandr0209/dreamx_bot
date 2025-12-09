# tournaments_debug.py
import bd
import tournaments_game_db as tgame
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL


def _get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def show(table, sql):
    conn = _get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            print(f"\n=== {table} ===")
            for r in rows:
                print(r)
    finally:
        conn.close()


def main():
    bd.init_pg_db()

    # 1) СТВОРЮЄМО ОДИН ТУРНІР У ТАБЛИЦІ tournaments
    conn = _get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO tournaments (title, prize, start_dt, status)
                VALUES (%s, %s, NOW(), 'scheduled')
                RETURNING id
                """,
                ("Test Турнір", "Test prize"),
            )
            tid = cur.fetchone()["id"]
            print("Створили турнір id =", tid)
    finally:
        conn.close()

    # 2) СТВОРЮЄМО КІЛЬКА КОРИСТУВАЧІВ + РЕЄСТРУЄМО ЇХ В ТУРНІРІ
    test_user_ids = [1001, 1002, 1003, 1004]

    for uid in test_user_ids:
        bd.ensure_user_pg(uid, f"user{uid}", f"User{uid}")
        tp_row = tgame.register_player(tid, uid)
        print("Зареєстрували в турнірі:", uid, "->", tp_row)

    # 3) СТВОРЮЄМО 1-Й РАУНД З ГРУПАМИ І МАТЧАМИ
    round_id = tgame.create_group_round_from_active(tid, round_number=1)
    print("Створили round_id =", round_id)

    # 4) ПОДИВИМОСЯ, ЩО Є В БАЗІ
    show("tournament_players", f"SELECT * FROM tournament_players WHERE tournament_id = {tid}")
    show("tournament_rounds", f"SELECT * FROM tournament_rounds WHERE tournament_id = {tid}")
    show("tournament_groups", f"SELECT * FROM tournament_groups WHERE tournament_id = {tid}")
    show("tournament_group_players", f"SELECT * FROM tournament_group_players WHERE tournament_id = {tid}")
    show("matches", f"SELECT * FROM matches WHERE tournament_id = {tid}")

    # 5) ВІЗЬМЕМО НАСТУПНИЙ МАТЧ ДЛЯ USER 1001 І ЗРОБИМО ХІД
    match = tgame.get_next_match_for_player(tid, 1001)
    print("\nНаступний матч для user 1001:", match)

    if match:
        print("Робимо хід user 1001: rock")
        res1 = tgame.submit_move(tid, match["id"], 1001, "rock")
        print("Після ходу 1001:", res1)

        print("Робимо хід суперника: scissors")
        # Визначаємо другого гравця по match
        other_tp_id = match["player2_id"] if res1.get("player1_delta") is None else match["player1_id"]
        # але простіше: знаємо, що в нас всього 2 гравці в цьому матчі
        tp1 = match["player1_id"]
        tp2 = match["player2_id"]

        # знайдемо, який user відповідає другому tournament_player_id
        conn = _get_conn()
        try:
            with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT player_id
                    FROM tournament_players
                    WHERE id = %s
                    """,
                    (tp2,),
                )
                other_user_id = cur.fetchone()["player_id"]
        finally:
            conn.close()

        res2 = tgame.submit_move(tid, match["id"], other_user_id, "scissors")
        print("Після ходу суперника:", res2)

        show("tournament_group_players (оновлені бали)",
             f"SELECT * FROM tournament_group_players WHERE tournament_id = {tid}")

    print("\nГотово.")


if __name__ == "__main__":
    main()
