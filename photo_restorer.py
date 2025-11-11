import base64
from openai import OpenAI
from aiogram.types import BufferedInputFile
from config import OPENROUTER_API_KEY
from aiogram import Bot
import logging


# 21.5 тг себестоимость 1 фото
# лимит 5$ - 3000 тг


class PhotoRestorer:
    """Класс для восстановления фото"""
    def __init__(self):
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
        self.standart_promt = "Restore and colorize this old or damaged photo. Remove photo frame and repair torn edges"
        self.model = "google/gemini-2.5-flash-image"
        
    async def restore(self, bot: Bot, file_path: str, user_promt: str = None):
        try:
            logging.info(f"🔄 Начало обработки: {file_path}")

            # скачивание изображение по file_id
            downloaded = await bot.download_file(file_path)
            img_bytes = downloaded.read()
            logging.info(f"📥 Скачано байт: {len(img_bytes)}")

            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            logging.info(f"🔐 Base64 закодировано")

            logging.info(f"📤 Отправка в OpenRouter...")
            # отправка изображения в нано банана. Универсальный вызов — через chat.completions
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_promt or self.standart_promt
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
            
            logging.info(f"✅ Получен ответ от OpenRouter")
            logging.info(f"📊 Тип ответа: {type(response)}")
            logging.info(f"📊 Choices: {len(response.choices)}")
            
            # получаем ответ от нано банана
            image_data_url = response.choices[0].message.images[0]["image_url"]["url"]
            image_b64 = image_data_url.split(",")[1]
            
            # Декодируем base64 в байты
            image_bytes = base64.b64decode(image_b64)
            logging.info(f"✅ Изображение декодировано, размер: {len(image_bytes)}")
            
            # Создаём буффер изображения напрямую из байтов
            photo_file = BufferedInputFile(image_bytes, filename="restored.png")

        except Exception as e:
            logging.error(f"⚠️ Ошибка при обработке изображения: {e}")
            return None
            
        else:
            return photo_file