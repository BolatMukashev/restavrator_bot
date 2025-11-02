from dotenv import dotenv_values


config = dotenv_values(".env")


# Конфигурация
TELEGRAM_BOT_TOKEN = config.get("TELEGRAM_BOT_TOKEN", None) or os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = config.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY")