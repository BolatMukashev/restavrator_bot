import json
from main import dp, bot, logger


async def handler(event, context):
    """Обработчик очереди (worker)"""
    messages = event.get("messages", [])
    logger.info(f"Worker получил {len(messages)} сообщений")

    for msg in messages:
        body_str = msg.get("details", {}).get("message", {}).get("body")

        if not body_str:
            continue

        logger.info(f"Worker BODY: {body_str}")

        try:
            body = json.loads(body_str)
        except Exception as e:
            logger.error(f"Ошибка парсинга body: {e}")
            continue

        if body.get("ping"):
            logger.info("⚙️ Получен ping — пропускаем")
            continue

        try:
            await dp.feed_webhook_update(bot=bot, update=body)
        except Exception as e:
            logger.error(f"Ошибка при обработке update: {e}")

