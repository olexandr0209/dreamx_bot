import logging
import json
import os  


from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from db import init_pg_db, get_or_create_pg, get_points_pg, add_points_pg, ensure_user_pg

from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from urllib.parse import urlparse, parse_qs

from config import BOT_TOKEN, DATABASE_URL, WEBAPP_URL

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    points = get_or_create_pg(user.id)

    # Тепер передаємо І user_id, І points
    url_with_points = f"{WEBAPP_URL}?user_id={user.id}&points={points}"


    # 🔹 клавіатура з ЗВИЧАЙНОЮ кнопкою (KeyboardButton), не inline
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
        resize_keyboard=True,      # кнопка компактна, як у мобільних чатах
        one_time_keyboard=False,   # не ховається після натискання (можна змінити)
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

class PointsAPI(BaseHTTPRequestHandler):

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    # ✅ OPTIONS для preflight CORS
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        # health-check для Render
        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(b"Bot is running")
            return

        # API: отримати бали
        if parsed.path == "/api/get_points":
            params = parse_qs(parsed.query)

            try:
                user_id = int(params.get("user_id", [0])[0])
            except (TypeError, ValueError):
                user_id = 0

            if not user_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.end_headers()
                self.wfile.write(b'{"error":"no_user_id"}')
                return

            # 🔥 КЛЮЧОВЕ МІСЦЕ — створюємо/читаємо користувача
            points = get_or_create_pg(user_id)

            result = json.dumps({"points": points}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(result)
            return

        # інші шляхи — 404
        self.send_response(404)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()


    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/add_points":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.end_headers()
                self.wfile.write(b'{"error":"invalid_json"}')
                return

            user_id = int(payload.get("user_id", 0))
            delta = int(payload.get("delta", 0))

            if not user_id or delta == 0:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.end_headers()
                self.wfile.write(b'{"error":"bad_parameters"}')
                return

            # ✅ оновлюємо БД
            add_points_pg(user_id, delta)
            points = get_points_pg(user_id)

            result = json.dumps({"ok": True, "points": points}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(result)

        elif parsed.path == "/api/ensure_user":
            # 🔹 Новий endpoint, який просто гарантує користувача в БД
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.end_headers()
                self.wfile.write(b'{"error":"invalid_json"}')
                return

            user_id = int(payload.get("user_id", 0))

            if not user_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.end_headers()
                self.wfile.write(b'{"error":"no_user_id"}')
                return

            # ✅ Гарантуємо, що юзер є в players
            ensure_user_pg(user_id)

            result = json.dumps({"ok": True}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(result)

        else:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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
