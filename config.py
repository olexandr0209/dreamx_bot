import os

# Який режим зараз: dev чи prod
APP_ENV = os.getenv("APP_ENV", "dev")

if APP_ENV == "prod":
    # Продакшн: головний бот
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL")
    WEBAPP_URL = "https://dreamx-webapp.onrender.com"
else:
    # Dev: тестовий бот
    BOT_TOKEN = os.getenv("BOT_TOKEN_DEV")
    DATABASE_URL = os.getenv("DATABASE_URL_DEV")
    WEBAPP_URL = "https://dreamx-webapp-dev.onrender.com"
