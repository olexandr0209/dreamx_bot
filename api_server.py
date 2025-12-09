# api_server.py — HTTP API для DreamX (points, giveaways, tournaments)

import logging
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import bd
import giveaway_db_from_admin as gdb
import tournaments_client_db as tdb
import tournaments_game_db as tgame  # <--- ДОДАНО

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")


class PointsAPI(BaseHTTPRequestHandler):

    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self._set_cors()
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # health-check
        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self._set_cors()
            self.end_headers()
            self.wfile.write(b"API is running")
            return

        # =============== GET_POINTS ==================
        if path == "/api/get_points":
            try:
                user_id = int(params.get("user_id", [0])[0])
            except (TypeError, ValueError):
                user_id = 0

            if not user_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"no_user_id"}')
                return

            points = bd.get_points_pg(user_id)
            result = json.dumps({"points": points}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors()
            self.end_headers()
            self.wfile.write(result)
            return

        # =============== GET_GIVEAWAYS ==================
        if path == "/api/get_giveaways":
            try:
                cards = gdb.get_active_cards()
                payload = json.dumps(
                    {"giveaways": cards},
                    default=str
                ).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(payload)
            except Exception as e:
                logger.exception("get_active_cards error: %s", e)
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"db_error"}')
            return

        # =============== GET_JOINED_GIVEAWAYS ==================
        if path == "/api/get_joined_giveaways":
            try:
                user_id = int(params.get("user_id", [0])[0])
            except (TypeError, ValueError):
                user_id = 0

            if not user_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"no_user_id"}')
                return

            try:
                rows = gdb.get_joined_giveaways_for_user(user_id)

                normal_ids = [
                    r["giveaway_id"]
                    for r in rows
                    if r.get("kind") == "normal"
                ]

                payload = json.dumps(
                    {
                        "joined": rows,
                        "joined_giveaway_ids": normal_ids
                    },
                    default=str
                ).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(payload)
                return

            except Exception as e:
                logger.exception("get_joined_giveaways error: %s", e)
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"db_error"}')
                return

        # =============== GET_TOURNAMENTS ==================
        if path == "/api/get_tournaments":
            try:
                tournaments = tdb.get_upcoming_tournaments(limit=20)
                payload = json.dumps(
                    {"tournaments": tournaments},
                    default=str
                ).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(payload)
            except Exception as e:
                logger.exception("get_tournaments error: %s", e)
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"db_error"}')
            return

        # =============== GET_TOURNAMENT (one) ==================
        if path == "/api/get_tournament":
            try:
                tid_raw = params.get("id", [None])[0]
                if tid_raw is None:
                    raise ValueError("id is required")

                tid = int(tid_raw)
                tournament = tdb.get_tournament_by_id(tid)

                if not tournament:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self._set_cors()
                    self.end_headers()
                    self.wfile.write(b'{"error":"not_found"}')
                    return

                payload = json.dumps(
                    {"tournament": tournament},
                    default=str
                ).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(payload)

            except ValueError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"bad_id"}')
            except Exception as e:
                logger.exception("get_tournament error: %s", e)
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"db_error"}')
            return

        # =============== GET_NEXT_MATCH (турнір) ==================
        if path == "/api/get_next_match":
            try:
                tournament_id = int(params.get("tournament_id", [0])[0])
                user_id = int(params.get("user_id", [0])[0])
            except (TypeError, ValueError):
                tournament_id = 0
                user_id = 0

            if not tournament_id or not user_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"bad_parameters"}')
                return

            try:
                match = tgame.get_next_match_for_player(tournament_id, user_id)
                payload = json.dumps(
                    {"match": match},
                    default=str
                ).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(payload)
                return
            except Exception as e:
                logger.exception("get_next_match error: %s", e)
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"db_error"}')
                return

        # 404
        self.send_response(404)
        self._set_cors()
        self.end_headers()

    # =====================================================
    #                   POST
    # =====================================================
    def do_POST(self):
        parsed = urlparse(self.path)

        # =============== ADD_POINTS ==================
        if parsed.path == "/api/add_points":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"invalid_json"}')
                return

            user_id = int(payload.get("user_id", 0))
            delta = int(payload.get("delta", 0))

            if not user_id or delta == 0:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"bad_parameters"}')
                return

            new_points = bd.add_points_and_return(user_id, delta)

            result = json.dumps({"ok": True, "points": new_points}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors()
            self.end_headers()
            self.wfile.write(result)
            return

        # =============== ENSURE_USER ==================
        if parsed.path == "/api/ensure_user":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"invalid_json"}')
                return

            user_id = int(payload.get("user_id", 0))

            if not user_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"no_user_id"}')
                return

            bd.ensure_user_pg(user_id, None, None)

            result = json.dumps({"ok": True}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors()
            self.end_headers()
            self.wfile.write(result)
            return

        # =============== JOIN_GIVEAWAY ==================
        if parsed.path == "/api/join_giveaway":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"invalid_json"}')
                return

            kind = payload.get("kind", "normal")

            try:
                giveaway_id = int(payload.get("giveaway_id", 0))
                user_id = int(payload.get("user_id", 0))
            except Exception:
                giveaway_id = 0
                user_id = 0

            username = payload.get("username") or None

            if not giveaway_id or not user_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"bad_parameters"}')
                return

            try:
                gdb.add_giveaway_player(
                    giveaway_id=giveaway_id,
                    user_id=user_id,
                    username_snapshot=username,
                    points_in_giveaway=1,
                    kind=kind,
                )

                result = json.dumps({"ok": True}).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(result)
                return

            except Exception as e:
                logger.exception("join_giveaway error: %s", e)
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"db_error"}')
                return

        # =============== JOIN_TOURNAMENT ==================
        if parsed.path == "/api/join_tournament":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"invalid_json"}')
                return

            try:
                tournament_id = int(payload.get("tournament_id", 0))
                user_id = int(payload.get("user_id", 0))
            except Exception:
                tournament_id = 0
                user_id = 0

            if not tournament_id or not user_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"bad_parameters"}')
                return

            try:
                row = tgame.register_player(tournament_id, user_id)
                resp = json.dumps(
                    {"ok": True, "tournament_player": row},
                    default=str
                ).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(resp)
                return

            except Exception as e:
                logger.exception("join_tournament error: %s", e)
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"db_error"}')
                return

        # =============== SUBMIT_MOVE (RPS) ==================
        if parsed.path == "/api/submit_move":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"invalid_json"}')
                return

            try:
                tournament_id = int(payload.get("tournament_id", 0))
                user_id = int(payload.get("user_id", 0))
                match_id = int(payload.get("match_id", 0))
                move = str(payload.get("move", "")).lower()
            except Exception:
                tournament_id = 0
                user_id = 0
                match_id = 0
                move = ""

            if not tournament_id or not user_id or not match_id or not move:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"bad_parameters"}')
                return

            try:
                result = tgame.submit_move(tournament_id, match_id, user_id, move)
                payload = json.dumps(
                    {"ok": True, "result": result},
                    default=str
               ).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(payload)
                return

            except ValueError as ve:
                logger.warning("submit_move logical error: %s", ve)
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                msg = json.dumps({"error": str(ve)}).encode("utf-8")
                self.wfile.write(msg)
                return

            except Exception as e:
                logger.exception("submit_move error: %s", e)
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(b'{"error":"db_error"}')
                return

        # 404
        self.send_response(404)
        self._set_cors()
        self.end_headers()


def run_api():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), PointsAPI)
    print(f"API server running on port {port}...")
    server.serve_forever()


if __name__ == "__main__":
    bd.init_pg_db()
    run_api()
