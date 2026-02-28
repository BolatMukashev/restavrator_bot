import base64
from openai import OpenAI
from aiogram.types import BufferedInputFile
from config import OPENROUTER_API_KEY
from aiogram import Bot
import logging
import json


# 35 тг себестоимость 1 фото на стандарт
# 70 тг себестоимость 1 фото на про
# лимит 5$ - 3000 тг


class PhotoRestorer:
    """Класс для восстановления фото"""
    def __init__(self):
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
        self.standart_promt = (
            "Restore and colorize this old or damaged photo."
            "Remove frame and fix torn edges."
            "Preserve facial features and people's recognizability."
        )
        self.pro_prompt = (
            "Restore and colorize this old or damaged photo with professional quality."
            "Generate at maximum possible resolution (2K/4K)."
            "Ultra-sharp details, perfect color grading."
            "Remove frame, fix torn edges, repair all damage."
            "Preserve exact facial features, identity and recognizability of all people."
        )
        self.model = "google/gemini-3.1-flash-image-preview"
        self.model_pro = "google/gemini-3-pro-image-preview"
        
    async def restore(self, bot: Bot, file_path: str, user_promt: str = None, pro: bool = False):
        model = self.model_pro if pro else self.model
        promt = self.pro_prompt if pro else self.standart_promt

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
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_promt or promt
                            },
                            {
                                "type": "image_url",
                                "image_url": f"data:image/png;base64,{img_b64}"
                            }
                        ],
                    }
                ],
                extra_body={
                            "generation_config": {
                                "response_mime_type": "image/png",
                                "image_config": {
                                    "aspect_ratio": "1:1",
                                    "resolution": "2048x2048"
                                }
                            }
                        }

            )

                        #     extra_body={
                        #     "size": "2048x2048",
                        #     "quality": "high"
                        # }

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