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

from db import init_pg_db, get_or_create_pg, get_points_pg, add_points_pg

from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from urllib.parse import urlparse, parse_qs


BOT_TOKEN = "8221786106:AAFa5dQNEeHM-lDbWJKObBzu6SHsZujUtPM"
WEBAPP_URL = "https://dreamx-webapp.onrender.com"


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    points = get_or_create_pg(user.id)

    # Додаємо параметр ?points=ХХ
    url_with_points = f"{WEBAPP_URL}?points={points}"

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

async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обробка даних, які приходять з WebApp через Telegram.WebApp.sendData(...)
    """
    message = update.effective_message
    user = update.effective_user

    if not message or not message.web_app_data:
        return

    raw_data = message.web_app_data.data
    print("RAW WEBAPP DATA:", raw_data)

    try:
        payload = json.loads(raw_data)
    except json.JSONDecodeError:
        print("⚠️ Не зміг розпарсити JSON з WebApp")
        return

    event_type = payload.get("type")
    if event_type == "WIN":
        delta = int(payload.get("delta", 1))

        # додаємо бали гравцеві в БД
        add_points_pg(user.id, delta)
        points = get_points_pg(user.id)

        print(f"✅ WIN від {user.id}, +{delta}, тепер {points} балів")
                # 🔹 НОВЕ: надсилаємо оновлену кнопку з актуальними балами
        url_with_points = f"{WEBAPP_URL}?points={points}"

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

        await message.reply_text(
            f"Зараховано +{delta} балів. Тепер у тебе {points} 🔥\n"
            f"Натисни кнопку нижче, щоб знову відкрити DreamX.",
            reply_markup=reply_kb,
        )

        # відповідати не обов'язково, щоб не спамити в чат
        # але якщо хочеш тестово:
        # await message.reply_text(f"Зараховано +{delta} бал(и). Тепер у тебе {points}.")

class PointsAPI(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        # 1) health-check для Render + UptimeRobot
        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Bot is running")
            return

        # 2) твій існуючий API
        if parsed.path == "/api/get_points":
            params = parse_qs(parsed.query)
            user_id = int(params.get("user_id", [0])[0])

            points = get_points_pg(user_id)
            result = json.dumps({"points": points}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(result)
        else:
            self.send_response(404)
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
    tg_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data_handler))

    # 4. Запускаємо HTTP API в окремому потоці
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    # 5. Запускаємо бота
    print("Bot is running (NEW VERSION)...")
    tg_app.run_polling()
