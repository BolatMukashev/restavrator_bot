from aiogram.utils.keyboard import InlineKeyboardBuilder


def payment_button(text: str):
    # кнопка оплатить
    builder = InlineKeyboardBuilder()
    builder.button(text=text, pay=True)
    
    return builder.as_markup()
