from urllib.parse import quote
from . import (
     ru_text, en_text, kk_text,
)

LANGUAGES = {
    "ru": {"TEXT": ru_text.TEXT, "BUTTONS_TEXT": ru_text.BUTTONS_TEXT, "NOTIFICATIONS": ru_text.NOTIFICATIONS},
    "en": {"TEXT": en_text.TEXT, "BUTTONS_TEXT": en_text.BUTTONS_TEXT, "NOTIFICATIONS": en_text.NOTIFICATIONS},
    "kk": {"TEXT": kk_text.TEXT, "BUTTONS_TEXT": kk_text.BUTTONS_TEXT, "NOTIFICATIONS": kk_text.NOTIFICATIONS},
}


async def get_texts(lang_code: str) -> dict:
    """Возвращает набор словарей по коду языка."""
    return LANGUAGES.get(lang_code, LANGUAGES["en"])
