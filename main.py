import base64
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import CommandStart
from aiogram.filters.command import Command
from openai import OpenAI
from aiogram.types import BufferedInputFile
from aiogram.types.input_paid_media_photo import InputPaidMediaPhoto
from config import TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY


# 21.5 тг себестоимость 1 фото


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


PRICE = 1


# ------------------------------------------------------------------------ ОБРАБОТКА ФОТО -----------------------------------------------------


class PhotoRestorer:
    """Класс для восстановления фото"""
    def __init__(self):
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
        self.promt = "Restore and colorize this old or damaged photo"
        self.model = "google/gemini-2.5-flash-image"
        
    async def restore(self, bot: Bot, file_path: str):
        try:
            # скачивание изображение по file_id
            downloaded = await bot.download_file(file_path)
            img_bytes = downloaded.read()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")

            # отправка изображения в нано банана. Универсальный вызов — через chat.completions
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self.promt
                            },
                            {
                                "type": "image_url",
                                "image_url": f"data:image/png;base64,{img_b64}"
                            }
                        ],
                    }
                ],
            )

            # 💾 Сохраняем весь ответ в файл
            # with open("response_full.txt", "w", encoding="utf-8") as f:
            #     json.dump(response.model_dump(), f, ensure_ascii=False, indent=2)

            # получаем ответ от нано банана
            image_data_url = response.choices[0].message.images[0]["image_url"]["url"]
            image_b64 = image_data_url.split(",")[1]
            
            # Декодируем base64 в байты
            image_bytes = base64.b64decode(image_b64)
            
            # Создаём буффер изображения напрямую из байтов
            photo_file = BufferedInputFile(image_bytes, filename="restored.png")

        except Exception as e:
            await logger.error(f"⚠️ Ошибка при обработке изображения: {e}")
            return None
            
        else:
            return photo_file


# ------------------------------------------------------------------------ ЛОГИКА --------------------------------------------------------


@commands_router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 Привет! Я бот для реставрации фотографий на основе OpenRouter AI.\n\n"
        "📸 Отправь мне старую или поврежденную фотографию, "
        "и я попробую её восстановить!\n\n"
        "✨ Я могу:\n"
        "• Убрать царапины и шум\n"
        "• Улучшить качество и резкость\n"
        "• Восстановить повреждённые участки\n"
        "• Улучшить цвета и контраст\n\n"
        "Просто пришли фото, и я начну работу!"
    )


@media_router.message(F.photo)
async def handle_photo(message: types.Message):
    await message.answer("🪄 Восстанавливаю фото, подожди немного...")

    # Скачиваем фото
    photo = message.photo[-1]
    # print(photo.file_id)
    file_id = await bot.get_file(photo.file_id)
    file_path = file_id.file_path
    
    photo_restorer = PhotoRestorer()
    photo_file = await photo_restorer.restore(bot, file_path)
    
    if photo_file is None:
        await message.answer("Ошибка при обработке изображения. Попробуйте отправить фото ещё раз")
    else:
        media = InputPaidMediaPhoto(media=photo_file, caption="Фото будет доступно после оплаты")
        await message.reply_paid_media(star_count=PRICE, media=[media],
                                       caption="✨ Готово!\nЧтобы сохранить опллоченное фото, перешлите его нашему боту @payed_photo_download_bot")


# ------------------------------------------------------------------------ ЗАПУСК --------------------------------------------------------


dp.include_router(commands_router)
dp.include_router(media_router)
dp.include_router(payment_router)


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

