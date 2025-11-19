import os

# Який режим зараз: dev чи prod
APP_ENV = os.getenv("APP_ENV", "dev")

if APP_ENV == "prod":
    # Продакшен: основний бот + основна база
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL")
else:
    # Dev: тестовий бот + тестова база (або та сама, якщо ти так зробив)
    BOT_TOKEN = os.getenv("BOT_TOKEN_DEV")
    DATABASE_URL = os.getenv("DATABASE_URL_DEV") or os.getenv("DATABASE_URL")
