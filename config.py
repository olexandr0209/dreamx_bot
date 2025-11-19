import os

# Який режим зараз: dev чи prod
APP_ENV = os.getenv("APP_ENV", "dev")

if APP_ENV == "prod":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
else:
    BOT_TOKEN = os.getenv("BOT_TOKEN_DEV")
