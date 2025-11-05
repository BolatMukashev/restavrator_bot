from aiogram import Bot, Dispatcher, types, F
from config import TELEGRAM_BOT_TOKEN


# отдельный бот


# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


@dp.message(F.photo)
async def handle_photo(message: types.Message):
    """Обработчик команды /test"""
    photo = message.photo[-1]
    await message.answer_photo(photo=photo.file_id, caption="✨ Готово! Это фото можно скачать")


@dp.message(~(F.photo))
async def delete_unwanted(message: types.Message):
    await message.answer("⚠️ Мы работаем только с фотографиями. Попробуйте отправить фото")