import logging
import os


# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


#ydb
MQ2_URL = os.environ.get("MQ2_URL")
KEY_ID = os.environ.get("KEY_ID")
SECRET_KEY = os.environ.get("SECRET_KEY")