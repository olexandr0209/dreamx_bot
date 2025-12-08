# api_server.py
import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import bd
import giveaway_db_from_admin as gdb
import tournaments_client_db as tdb

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class ApiHandler(BaseHTTPRequestHandler):

    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    # -------- HEAD / OPTIONS --------

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self._set_cors()
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    # ----------------- GET -----------------

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
            self.wfile.write(b"DreamX API running")
            return

        # ---- /api/get_points ----
        if path == "/api/get_points":
            try:
                user_id = int(params.get("user_id", [0])[0])
            except (TypeError, ValueError):
                user_id = 0

            if not user_id:
                self._json_error(400, "no_user_id")
                return

            points = bd.get_points_pg(user_id)
            self._json_ok({"points": points})
            return

        # ---- /api/get_giveaways ----
        if path == "/api/get_giveaways":
            try:
                cards = gdb.get_active_cards()
                self._json_ok({"giveaways": cards})
            except Exception as e:
                logger.exception("get_active_cards error: %s", e)
                self._json_error(500, "db_error")
            return

        # ---- /api/get_joined_giveaways ----
        if path == "/api/get_joined_giveaways":
            try:
                user_id = int(params.get("user_id", [0])[0])
            except (TypeError, ValueError):
                user_id = 0

            if not user_id:
                self._json_error(400, "no_user_id")
                return

            try:
                rows = gdb.get_joined_giveaways_for_user(user_id)

                normal_ids = [
                    r["giveaway_id"]
                    for r in rows
                    if r.get("kind") == "normal"
                ]

                self._json_ok(
                    {
                        "joined": rows,
                        "joined_giveaway_ids": normal_ids,
                    }
                )
            except Exception as e:
                logger.exception("get_joined_giveaways error: %s", e)
                self._json_error(500, "db_error")
            return

        # ---- /api/get_tournaments ----
        if path == "/api/get_tournaments":
            try:
                tournaments = tdb.list_upcoming(limit=20)
                self._json_ok({"tournaments": tournaments})
            except Exception as e:
                logger.exception("get_tournaments error: %s", e)
                self._json_error(500, "db_error")
            return

        # ---- /api/get_tournament?id=... ----
        if path == "/api/get_tournament":
            try:
                tid_raw = params.get("id", [None])[0]
                if tid_raw is None:
                    raise ValueError("id is required")

                tid = int(tid_raw)
                tournament = tdb.get_tournament_by_id(tid)

                if not tournament:
                    self._json_error(404, "not_found")
                    return

                self._json_ok({"tournament": tournament})
            except ValueError:
                self._json_error(400, "bad_id")
            except Exception as e:
                logger.exception("get_tournament error: %s", e)
                self._json_error(500, "db_error")
            return

        # 404
        self.send_response(404)
        self._set_cors()
        self.end_headers()
        self.wfile.write(b"Not Found")

    # ----------------- POST -----------------

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # ---- helper для читання JSON ----
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._json_error(400, "invalid_json")
            return

        # ---- /api/add_points ----
        if path == "/api/add_points":
            user_id = int(payload.get("user_id", 0))
            delta = int(payload.get("delta", 0))

            if not user_id or delta == 0:
                self._json_error(400, "bad_parameters")
                return

            new_points = bd.add_points_and_return(user_id, delta)
            self._json_ok({"ok": True, "points": new_points})
            return

        # ---- /api/ensure_user ----
        if path == "/api/ensure_user":
            user_id = int(payload.get("user_id", 0))

            if not user_id:
                self._json_error(400, "no_user_id")
                return

            bd.ensure_user_pg(user_id, None, None)
            self._json_ok({"ok": True})
            return

        # ---- /api/join_giveaway ----
        if path == "/api/join_giveaway":
            kind = payload.get("kind", "normal")

            try:
                giveaway_id = int(payload.get("giveaway_id", 0))
                user_id = int(payload.get("user_id", 0))
            except Exception:
                giveaway_id = 0
                user_id = 0

            username = payload.get("username") or None

            if not giveaway_id or not user_id:
                self._json_error(400, "bad_parameters")
                return

            try:
                gdb.add_giveaway_player(
                    giveaway_id=giveaway_id,
                    user_id=user_id,
                    username_snapshot=username,
                    points_in_giveaway=1,
                    kind=kind,
                )
                self._json_ok({"ok": True})
            except Exception as e:
                logger.exception("join_giveaway error: %s", e)
                self._json_error(500, "db_error")
            return

        # 404
        self.send_response(404)
        self._set_cors()
        self.end_headers()
        self.wfile.write(b"Not Found")

    # ----------------- helpers -----------------

    def _json_ok(self, data: dict):
        payload = json.dumps(data, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors()
        self.end_headers()
        self.wfile.write(payload)

    def _json_error(self, status: int, code: str):
        payload = json.dumps({"error": code}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors()
        self.end_headers()
        self.wfile.write(payload)


def run_api():
    # ініціалізувати БД на всяк випадок
    bd.init_pg_db()

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), ApiHandler)
    print(f"DreamX API server running on port {port}...")
    server.serve_forever()


if __name__ == "__main__":
    run_api()
