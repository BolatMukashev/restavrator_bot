import os
from dotenv import dotenv_values


config = dotenv_values(".env")


# Конфигурация
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or config.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY =  os.environ.get("OPENROUTER_API_KEY") or config.get("OPENROUTER_API_KEY")

YDB_PATH = os.environ.get("YDB_PATH") or config.get("YDB_PATH")
YDB_ENDPOINT = os.environ.get("YDB_ENDPOINT") or config.get("YDB_ENDPOINT")
YDB_TOKEN = os.environ.get("YDB_TOKEN") or config.get("YDB_TOKEN")

AMOUNT = 1

ADMIN = os.environ.get("ADMIN") or config.get("ADMIN")
