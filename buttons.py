from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def payment_button(text: str):
    # кнопка оплатить
    builder = InlineKeyboardBuilder()
    builder.button(text=text, pay=True)
    
    return builder.as_markup()


async def get_payment_buttons(text: dict, amount: int, file_id: str):

    button = InlineKeyboardButton(text=text, callback_data=f"pay|{amount}|{file_id}")
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])
    
    return markup