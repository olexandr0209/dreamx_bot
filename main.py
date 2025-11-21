import logging
import json
import os

import bd
from bd import (
    init_pg_db,
    get_points_pg,
    add_points_pg,
    ensure_user_pg,
    get_or_create_user_points,
)

from telegram import (
    Update,
    WebAppInfo,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from urllib.parse import urlparse, parse_qs

from config import BOT_TOKEN, DATABASE_URL, WEBAPP_URL

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# =========================
#   TELEGRAM BOT HANDLERS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # 🔥 створюємо або читаємо користувача з БД
    points = get_or_create_user_points(user.id)

    # Передаємо user_id і points в URL (можеш потім points прибрати,
    # якщо фронт повністю переходить на API /api/get_points)
    url_with_points = f"{WEBAPP_URL}?user_id={user.id}&points={points}"

    keyboard = [
        [
            KeyboardButton(
                text="🚀 Open DreamX App",
                web_app=WebAppInfo(url=url_with_points),
            )
        ]
    ]

    reply_kb = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
    )

    await update.message.reply_text(
        f"Привіт, {user.first_name}!\n"
        f"Твої бали: {points}\n\n"
        f"Натисни кнопку нижче, щоб відкрити DreamX WebApp:",
        reply_markup=reply_kb,
    )


async def mypoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    points = get_points_pg(user.id)

    await update.message.reply_text(
        f"У тебе зараз {points} балів 🔥"
    )


# =========================
#   HTTP API (POINTS)
# =========================

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

    # ✅ OPTIONS для preflight CORS
    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        # health-check для Render
        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self._set_cors()
            self.end_headers()
            self.wfile.write(b"Bot is running")
            return

        # ✅ API: отримати бали (автоматично створює юзера, якщо його нема)
        if parsed.path == "/api/get_points":
            params = parse_qs(parsed.query)

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

            # 🔥 ключ: створюємо або отримуємо користувача
            points = bd.get_or_create_user_points(user_id)

            result = json.dumps({"points": points}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors()
            self.end_headers()
            self.wfile.write(result)
            return

        # інші шляхи — 404
        self.send_response(404)
        self._set_cors()
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)

        # ✅ Додати бали користувачу
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

            # ✅ оновлюємо БД
            add_points_pg(user_id, delta)
            points = get_points_pg(user_id)

            result = json.dumps({"ok": True, "points": points}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors()
            self.end_headers()
            self.wfile.write(result)
            return

        # ✅ Просто гарантуємо, що юзер існує
        elif parsed.path == "/api/ensure_user":
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

            ensure_user_pg(user_id)

            result = json.dumps({"ok": True}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors()
            self.end_headers()
            self.wfile.write(result)
            return

        else:
            self.send_response(404)
            self._set_cors()
            self.end_headers()


def run_api():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), PointsAPI)
    print(f"API server running on port {port}...")
    server.serve_forever()


if __name__ == "__main__":
    # 1. Створюємо таблицю, якщо її ще нема
    init_pg_db()

    # 2. Створюємо застосунок Telegram
    tg_app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 3. Реєструємо команди
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("mypoints", mypoints))

    # 4. Запускаємо HTTP API в окремому потоці
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    # 5. Запускаємо бота
    print("Bot is running (NEW VERSION)...")
    tg_app.run_polling()
