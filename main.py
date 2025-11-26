import logging
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import giveaway_db_from_admin as gdb

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

import bd
from config import BOT_TOKEN, WEBAPP_URL

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

ADMIN_IDS = [929619425]  # твій Telegram ID, додай інші при потребі

# =========================
#   TELEGRAM BOT HANDLERS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # 🔥 ВАЖЛИВО: одна й та ж логіка, що й для гри
    points = bd.get_points_pg(user.id)

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
    points = bd.get_points_pg(user.id)

    await update.message.reply_text(
        f"У тебе зараз {points} балів 🔥"
    )

async def pm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /pm <user_id> <текст>

    Приклад:
    /pm 123456789 Вітаю, ти виграв у DreamX! 🎉
    """
    user = update.effective_user

    # 🔒 тільки адміни можуть користуватись цією командою
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("У тебе немає прав використовувати цю команду.")
        return

    # треба мінімум 2 аргументи: id + текст
    if len(context.args) < 2:
        await update.message.reply_text(
            "Формат:\n"
            "/pm <user_id> <повідомлення>\n\n"
            "Приклад:\n"
            "/pm 123456789 Вітаю, ти виграв! 🎉"
        )
        return

    # перший аргумент — це user_id
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("user_id має бути числом.")
        return

    # все, що після user_id — текст повідомлення
    text = " ".join(context.args[1:])

    try:
        await context.bot.send_message(chat_id=target_user_id, text=text)
        await update.message.reply_text("Повідомлення надіслано ✅")
    except Exception as e:
        await update.message.reply_text(
            "Не вдалося надіслати повідомлення.\n"
            "Можливо, користувач ще не натискав /start у боті.\n"
            f"Помилка: {e}"
        )


#================== Карточка з бази даних ================= # 




async def test_giveaways(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Тест: показати активні розіграші та оголошення,
    які бачить ігровий бот із загальної БД.
    """
    user = update.effective_user

    # 1) активні розіграші
    giveaways = gdb.get_active_giveaways()
    promo = gdb.get_active_promo_giveaways()
    anns = gdb.get_active_announcements()

    lines = [f"👋 Привіт, {user.first_name}!",
             "Ось що зараз є в системі:\n"]

    if giveaways:
        lines.append("🎁 *Активні звичайні розіграші:*")
        for g in giveaways:
            lines.append(
                f"- `#{g['id']}` {g['title']} — приз: *{g['prize']}* "
                f"(до {g['prize_count']} переможців), до {g['end_at']:%d.%m %H:%M}"
            )
        lines.append("")  # пуста строка
    else:
        lines.append("Немає активних звичайних розіграшів.\n")

    if promo:
        lines.append("📣 *Активні промо-розіграші каналів:*")
        for p in promo:
            lines.append(
                f"- `#{p['id']}` {p['title']} — приз: *{p['prize']}* "
                f"(до {p['prize_count']}), до {p['end_at']:%d.%m %H:%M}"
            )
        lines.append("")
    else:
        lines.append("Немає активних промо-розіграшів.\n")

    if anns:
        lines.append("📌 *Активні оголошення:*")
        for a in anns:
            lines.append(
                f"- `#{a['id']}` {a['title']} (до {a['end_at']:%d.%m %H:%M})"
            )
    else:
        lines.append("Немає активних оголошень.")

    text = "\n".join(lines)

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
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

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        # health-check
        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self._set_cors()
            self.end_headers()
            self.wfile.write(b"Bot is running")
            return

        # ✅ Отримати звичайні бали (points)
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

            points = bd.get_points_pg(user_id)

            result = json.dumps({"points": points}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors()
            self.end_headers()
            self.wfile.write(result)
            return

        # ✅ Отримати турнірні бали (points_tour)
        if parsed.path == "/api/get_tour_points":
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

            # окрема функція для читання points_tour
            points_tour = bd.get_tour_points_pg(user_id)

            result = json.dumps({"points_tour": points_tour}).encode("utf-8")

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

        # ✅ Додати звичайні бали (points)
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

        # ✅ Додати турнірні бали (points_tour)
        elif parsed.path == "/api/add_tour_points":
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

            # окрема функція для points_tour
            new_points_tour = bd.add_tour_points_and_return(user_id, delta)

            result = json.dumps(
                {"ok": True, "points_tour": new_points_tour}
            ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors()
            self.end_headers()
            self.wfile.write(result)
            return

        # ✅ Просто гарантуємо, що юзер є
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

            bd.ensure_user_pg(user_id)

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
    bd.init_pg_db()

    # 2. Telegram app
    tg_app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 3. Команди
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("mypoints", mypoints))
    tg_app.add_handler(CommandHandler("pm", pm_command))
    tg_app.add_handler(CommandHandler("test_giveaways", test_giveaways))  # 👈 ДОДАТИ ЦЮ ЛІНІЮ


    # 4. HTTP API в окремому потоці
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    # 5. Запускаємо бота
    print("Bot is running (NEW VERSION)...")
    tg_app.run_polling()
