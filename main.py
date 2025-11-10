import asyncio
import logging
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import CommandStart
from aiogram.filters.command import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from buttons import *
from languages import get_texts, desc
from config import TELEGRAM_BOT_TOKEN, AMOUNT, ADMIN
from photo_restorer import PhotoRestorer
from ydb_models import *
from languages.desc import DESCRIPTIONS, SHORT_DESCRIPTIONS, NAMES


# ------------------------------------------------------------------------ НАСТРОЙКА --------------------------------------------------------


# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


commands_router = Router()
media_router = Router()
payment_router = Router()


# установка описания
@dp.message(Command("set_description"))
async def cmd_set_description(message: types.Message):
    user_id = message.from_user.id
    if user_id == ADMIN:
        # установка описания для бота на разных языках
        for lang, text in DESCRIPTIONS.items():
            try:
                await bot.set_my_description(description=text, language_code=lang)
            except Exception as e:
                print(f"Ошбика установки описания для языка {lang} - {e}")
            else:
                print("Описание для бота установлено ✅")

        # установка короткого описания для бота на разных языках
        for lang, text in SHORT_DESCRIPTIONS.items():
            try:
                await bot.set_my_short_description(short_description=text, language_code=lang)
            except Exception as e:
                print(f"Ошбика установки короткого описания для языка {lang} - {e}")
            else:
                print("Короткое описание для бота установлено ✅")

        # установка имени бота на разных языках
        for lang, name in NAMES.items():
            try:
                await bot.set_my_name(name=name, language_code=lang)
            except Exception as e:
                print(f"Ошбика установки имени для языка {lang} - {e}")
            else:
                print("Название бота установлено ✅")


# ------------------------------------------------------------------------ ЛОГИКА --------------------------------------------------------


@commands_router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    user_lang = message.from_user.language_code
    texts = await get_texts(user_lang)

    # добавление пользователя в бд
    async with UserClient() as user_client:
        user = User(user_id, full_name, user_lang)
        await user_client.insert_user(user)
    
    await message.answer(texts["TEXT"]["start"])


@media_router.message(F.photo | F.document)
async def handle_photo_or_document(message: types.Message):
    user_id = message.from_user.id
    user_lang = message.from_user.language_code
    message_id = message.message_id
    texts = await get_texts(user_lang)
    caption = message.caption

    # Определяем тип вложения
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "image"
    elif message.document and message.document.mime_type in {"image/jpeg", "image/png"}:
        file_id = message.document.file_id
        file_type = "file_image"
    else:
        await message.answer(texts["TEXT"]["error_not_image"])
        return

    # Получаем данные пользователя
    async with UserClient() as user_client:
        user = await user_client.get_user_by_id(user_id)

    # Бесплатная генерация
    if user.free_generate:
        notif_mess = await message.answer(texts["TEXT"]["photo_accepted"])

        # получение и обработка фотографии
        file_info = await bot.get_file(file_id)
        file_path = file_info.file_path

        photo_restorer = PhotoRestorer()
        photo_file = await photo_restorer.restore(bot, file_path, caption)

        if photo_file is None:
            await message.answer(texts["TEXT"]["generation_error"])
        else:
            if file_type == "image":
                await message.answer_photo(photo=photo_file, caption=texts["TEXT"]["photo_is_ready"], reply_to_message_id=message_id)
            else:
                await message.answer_document(document=photo_file, reply_to_message_id=message_id)

            # Блокируем дальнейшие бесплатные генерации
            async with UserClient() as user_client:
                await user_client.update_field_free_generate(user_id, False)

        await bot.delete_message(user_id, notif_mess.message_id)

    else:
        label = texts["TEXT"]["payment"]["label"]
        title = texts["TEXT"]["payment"]["title"]
        description = texts["TEXT"]["payment"]["description"]

        prices = [types.LabeledPrice(label=label, amount=AMOUNT)]

        pay_message = await message.answer_invoice(
            title=title,
            description=description,
            payload=f"payment|{AMOUNT}|{message_id}|{file_type}",
            provider_token="",
            currency="XTR",
            prices=prices,
            reply_markup=payment_button(texts["BUTTONS_TEXT"]["pay"].format(amount=AMOUNT)),
            reply_to_message_id=message_id
        )

        # сохраняем в Кэш "ссылку" на фото
        async with CacheClient() as cache_client:
            new_cache = Cache(user_id, message_id, file_id, pay_message.message_id)
            await cache_client.insert_cache(new_cache)


# ------------------------------------------------------------------- ОПЛАТА -------------------------------------------------------


@payment_router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@payment_router.message(F.successful_payment)
async def on_successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    user_id = message.from_user.id
    user_lang = message.from_user.language_code
    caption = message.caption

    texts = await get_texts(user_lang) # получение текста на языке пользователя
    
    _, amount, message_id_str, file_type = payload.split("|") # получение данных

    # добавление платежа в бд
    async with PaymentClient() as payment_client:
        new_payment = Payment(user_id, int(message_id_str), int(amount), PaymentType.RESTORATION.value)
        await payment_client.insert_payment(new_payment)

    # получаем кэш
    async with CacheClient() as cache_client:
        cache = await cache_client.get_cache_by_telegram_id(user_id)
    
    cache = cache.get(int(message_id_str))
    file_id = cache.get("photo")
    pay_message_id = cache.get("pay_message_id")

    # сообщение о приеме платежа
    notif_mess = await message.answer(texts["TEXT"]["payment"]["payment_accepted"])

    # удаление сообщения об оплате
    try:
        await bot.delete_message(user_id, pay_message_id)
    except Exception as e:
        print("Ошибка удаления сообщений:", e)

    # получение и обработка фотографии
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    
    photo_restorer = PhotoRestorer()

    try:
        photo_file = await photo_restorer.restore(bot, file_path, caption)
    except Exception as e:
        print("Ошибка при обработке изображения Nano Banano:", e)
        photo_file = None
    
    if photo_file is None:
        await message.answer(texts["TEXT"]["generation_error"])
        
        # +1 генерация
        async with UserClient() as user_client:
            await user_client.update_field_free_generate(user_id, True)
    else:
        if file_type == "image":
            await message.answer_photo(photo=photo_file, caption=texts["TEXT"]["photo_is_ready"], reply_to_message_id=int(message_id_str))
        else:
            await message.answer_document(document=photo_file, reply_to_message_id=int(message_id_str))
    
    # подчищаем мусор
    async with CacheClient() as cache_client:
        await cache_client.delete_cache_by_telegram_id_and_photo_message_id(user_id, int(message_id_str))

    try:
        await bot.delete_message(user_id, notif_mess.message_id)
    except Exception as e:
        print("Ошибка удаления сообщений:", e)


# ------------------------------------------------------------------------ ДРУГИЕ ФОРМАТЫ --------------------------------------------------------


@dp.message(~(F.document | F.photo | F.successful_payment))
async def delete_unwanted(message: types.Message):
    try:
        await message.delete()
    except Exception as e:
        print(f"⚠️ Не удалось удалить сообщение: {e}")


# ------------------------------------------------------------------------ ЗАПУСК --------------------------------------------------------


dp.include_router(payment_router)
dp.include_router(commands_router)
dp.include_router(media_router)


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

