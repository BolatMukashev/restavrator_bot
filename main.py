import asyncio
import logging
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile
from buttons import *
from languages import get_texts, desc
from config import TELEGRAM_BOT_TOKEN, AMOUNT
from photo_restorer import PhotoRestorer


# ------------------------------------------------------------------------ НАСТРОЙКА --------------------------------------------------------


# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


commands_router = Router()
media_router = Router()
payment_router = Router()


cache = {}


# ------------------------------------------------------------------------ ЛОГИКА --------------------------------------------------------


@commands_router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_lang = message.from_user.language_code
    texts = await get_texts(user_lang)
    
    await message.answer(texts["TEXT"]["start"])


@media_router.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    user_lang = message.from_user.language_code
    message_id = message.message_id
    texts = await get_texts(user_lang)

    file_id = message.photo[-1].file_id
    print(type(file_id), file_id)
    
    # сохранить в кэш user_id, message_id, file_id
    cache[message_id] = file_id

    label = texts["TEXT"]["payment"]["label"]
    title = texts["TEXT"]["payment"]["title"]
    description = texts["TEXT"]["payment"]["description"].format(amount=AMOUNT)

    prices = [types.LabeledPrice(label=label, amount=AMOUNT)]

    sent_invoice = await message.answer_invoice(
        title=title,
        description=description,
        payload=f"payment|{AMOUNT}|{message_id}",
        provider_token="",
        currency="XTR",
        prices=prices,
        reply_markup=payment_button(texts["BUTTONS_TEXT"]["pay"])
    )

    # сохраняем в Кэш
    # async with CacheClient() as cache_client:
    #     new_cache = Cache(user_id, "payment_message_id", sent_invoice.message_id)
    #     await cache_client.insert_cache(new_cache)

    # await callback.answer(texts["NOTIFICATIONS"]["payment_sent"])

    # markup = await get_payment_buttons(texts["BUTTONS_TEXT"]["amount"].format(amount=AMOUNT), AMOUNT, message_id)

    # await message.answer(texts["TEXT"]["payment"]["intention"], reply_markup=markup, reply_to_message_id=message.message_id)


# ------------------------------------------------------------------- ОПЛАТА -------------------------------------------------------


@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@dp.message(lambda message: message.successful_payment is not None)
async def on_successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    user_id = message.from_user.id
    user_lang = message.from_user.language_code

    # получение текста на языке пользователя
    texts = await get_texts(user_lang)
    
    _, amount, message_id_str = payload.split("|")

    # async with PaymentClient() as payment_client:
    #     new_payment = Payment(user_id, int(amount), ref_code)
    #     await payment_client.insert_payment(new_payment)

    # Скачиваем фото
    await message.answer(texts["TEXT"]["payment"]["payment_accepted"])

    file_id = cache[int(message_id_str)]

    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    
    photo_restorer = PhotoRestorer()
    photo_file = await photo_restorer.restore(bot, file_path)
    
    if photo_file is None:
        await message.answer("Ошибка при обработке изображения. Попробуйте отправить фото ещё раз")
    else:
        await message.answer_photo(photo=photo_file, caption=texts["TEXT"]["photo_is_ready"], reply_to_message_id=int(message_id_str))


    # удаление старого сообщения
    # async with CacheClient() as cache_client:
    #     cached_messages = await cache_client.get_cache_by_telegram_id(user_id)
    #     payment_message_id = cached_messages.get("payment_message_id")


# ------------------------------------------------------------------------ ЗАПУСК --------------------------------------------------------


dp.include_router(commands_router)
dp.include_router(media_router)


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

