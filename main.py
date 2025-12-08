# main.py — тільки Telegram-бот DreamX

import logging

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
import giveaway_db_from_admin as gdb
from config import BOT_TOKEN, WEBAPP_URL  # <-- беремо звідси

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

ADMIN_IDS = [929619425]


# =========================
#   HANDLERS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Got /start from %s (%s)", user.id, user.username)

    bd.ensure_user_pg(
        user_id=user.id,
        user_name=user.username,
        first_name=user.first_name
    )

    points = bd.get_points_pg(user.id)
    url_with_points = f"{WEBAPP_URL}?user_id={user.id}&points={points}"

    keyboard = [[
        KeyboardButton(
            text="🚀 Open DreamX App",
            web_app=WebAppInfo(url=url_with_points),
        )
    ]]

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
    await update.message.reply_text(f"У тебе зараз {points} балів 🔥")


async def pm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id not in ADMIN_IDS:
        await update.message.reply_text("У тебе немає прав використовувати цю команду.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Формат:\n"
            "/pm <user_id> <повідомлення>\n\n"
            "Приклад:\n"
            "/pm 123456789 Вітаю, ти виграв! 🎉"
        )
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("user_id має бути числом.")
        return

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


async def test_giveaways(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

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
                f"(до {g['prize_count']} переможців), "
                f"до {g['end_at']:%d.%m %H:%M}"
            )
        lines.append("")
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
    await update.message.reply_text(text, parse_mode="Markdown")


if __name__ == "__main__":
    bd.init_pg_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mypoints", mypoints))
    app.add_handler(CommandHandler("pm", pm_command))
    app.add_handler(CommandHandler("test_giveaways", test_giveaways))

    print("Bot is running (BOT ONLY)...")
    app.run_polling()
