import os
from dotenv import dotenv_values


config = dotenv_values(".env")


# Конфигурация
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or config.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY =  os.environ.get("OPENROUTER_API_KEY") or config.get("OPENROUTER_API_KEY")

AMOUNT = 1
