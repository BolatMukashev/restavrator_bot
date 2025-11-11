import asyncio
import ydb
import ydb.aio
from typing import Optional, Dict, Any
from config import YDB_ENDPOINT, YDB_PATH, YDB_TOKEN
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


# yc iam create-token   (12 часов действует)
# ngrok http 127.0.0.1:8080 - поднять webhood локально на 8080 порту
# пропускная способность базы - 50 запросов/секунду сейчас


__all__ = ['User',
           'UserClient',
           'Cache',
           'CacheClient',
           'Payment',
           'PaymentClient',
           'PaymentType',
           'YDBClient'
           ]


class PaymentType(Enum):
    RESTORATION = "restoration"
    ANIMATION = "animation"


# ---------------------------------------------------------- БАЗОВЫЙ КЛАСС ---------------------------------------------------------


class YDBClient:
    def __init__(self, endpoint: str = YDB_ENDPOINT, database: str = YDB_PATH, token: str = YDB_TOKEN):
        """
        Инициализация клиента YDB
        """
        self.endpoint = endpoint
        self.database = database
        self.token = token
        self.driver = None
        self.pool = None
        self.credentials = ydb.AccessTokenCredentials(self.token) # ydb.iam.MetadataUrlCredentials() # 
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def connect(self):
        """
        Создание соединения с YDB и инициализация пула сессий
        """
        if self.driver is not None:
            return  # уже подключены
            
        driver_config = ydb.DriverConfig(
            self.endpoint, 
            self.database,
            credentials=self.credentials,
            root_certificates=ydb.load_ydb_root_certificate(),
        )
        
        self.driver = ydb.aio.Driver(driver_config)
        
        try:
            await self.driver.wait(timeout=5)
            self.pool = ydb.aio.QuerySessionPool(self.driver)
            print("Successfully connected to YDB")
        except TimeoutError:
            print("Connect failed to YDB")
            print("Last reported errors by discovery:")
            print(self.driver.discovery_debug_details())
            await self.driver.stop()
            self.driver = None
            raise
    
    async def close(self):
        """
        Закрытие соединения с YDB
        """
        if self.pool:
            await self.pool.stop()
            self.pool = None
        
        if self.driver:
            await self.driver.stop()
            self.driver = None
            print("YDB connection closed")
    
    def _ensure_connected(self):
        """
        Проверка, что соединение установлено
        """
        if self.driver is None or self.pool is None:
            raise RuntimeError("YDB client is not connected. Call connect() first or use as async context manager.")
    
    async def table_exists(self, table_name: str) -> bool:
        """
        Проверка существования таблицы
        """
        self._ensure_connected()
        try:
            await self.pool.execute_with_retries(f"SELECT 1 FROM `{table_name}` LIMIT 0;")
            return True
        except ydb.GenericError:
            return False
    
    async def create_table(self, table_name: str, schema: str):
        """
        Создание таблицы с заданной схемой (если она не существует)
        """
        self._ensure_connected()
        print(f"\nChecking if table {table_name} exists...")
        try:
            await self.pool.execute_with_retries(schema)
            print(f"Table {table_name} created successfully!")
        except ydb.GenericError as e:
            if "path exist" in str(e):
                print(f"Table {table_name} already exists, skipping creation.")
            else:
                raise e
    
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None):
        """
        Выполнение произвольного запроса
        """
        self._ensure_connected()
        return await self.pool.execute_with_retries(query, params)
    
    async def clear_all_tables(self):
        """Удаляет все записи во всех таблицах"""
        self._ensure_connected()

        tables = [
            "users",
            "payments",
            "cache",
        ]

        for table in tables:
            try:
                await self.execute_query(f"DELETE FROM `{table}`;")
                print(f"Таблица {table} очищена.")
            except Exception as e:
                print(f"Ошибка при очистке {table}: {e}")


# ------------------------------------------------------------ АНКЕТА -----------------------------------------------------------


@dataclass
class User:
    telegram_id: int
    full_name: Optional[str] = None
    language_code: Optional[str] = None
    free_generate: bool = True
    created_at: Optional[int] = None  # Храним как timestamp (секунды с эпохи)  


class UserClient(YDBClient):
    def __init__(self, endpoint: str = YDB_ENDPOINT, database: str = YDB_PATH, token: str = YDB_TOKEN):
        super().__init__(endpoint, database, token)
        self.table_name = "users"
        self.table_schema = """
            CREATE TABLE `users` (
                `telegram_id` Uint64 NOT NULL,
                `full_name` Utf8,
                `language_code` Utf8,
                `free_generate` Bool,
                `created_at` Uint64,
                PRIMARY KEY (`telegram_id`)
            )
        """
    
    async def create_users_table(self):
        """Создание таблицы users"""
        await self.create_table(self.table_name, self.table_schema)
    
    async def insert_user(self, user: User) -> User:
        """Вставка или обновление пользователя (UPSERT) и возврат объекта User"""

        existing_user = await self.get_user_by_id(user.telegram_id)

        # Если пользователь уже есть, сохраняем текущее значение free_generate
        if existing_user is not None:
            user.free_generate = existing_user.free_generate

        if user.created_at is None:
            user.created_at = int(datetime.now(timezone.utc).timestamp())

        await self.execute_query(
            """
            DECLARE $telegram_id AS Uint64;
            DECLARE $full_name AS Utf8?;
            DECLARE $language_code AS Utf8?;
            DECLARE $free_generate AS Bool;
            DECLARE $created_at AS Uint64?;

            UPSERT INTO users (
                telegram_id, full_name, language_code, free_generate, created_at
            ) VALUES (
                $telegram_id, $full_name, $language_code, $free_generate, $created_at
            );
            """,
            self._to_params(user)
        )
        return await self.get_user_by_id(user.telegram_id)

    async def get_user_by_id(self, telegram_id: int) -> Optional[User]:
        """Получение пользователя по telegram_id"""
        result = await self.execute_query(
            """
            DECLARE $telegram_id AS Uint64;
            SELECT telegram_id, full_name, language_code, free_generate, created_at
            FROM users
            WHERE telegram_id = $telegram_id;
            """,
            {"$telegram_id": (telegram_id, ydb.PrimitiveType.Uint64)}
        )

        rows = result[0].rows
        if not rows:
            return None

        return self._row_to_user(rows[0])
    
    async def update_field_free_generate(self, telegram_id: int, free_generate: bool):
        """Обновление поля free_generate по telegram_id"""

        query = f"""
            DECLARE $telegram_id AS Uint64;
            DECLARE $free_generate AS Bool;

            UPDATE users
            SET free_generate = $free_generate
            WHERE telegram_id = $telegram_id;
        """
        params = {"$telegram_id": (telegram_id, ydb.PrimitiveType.Uint64),
                  "$free_generate": (free_generate, ydb.PrimitiveType.Bool)}

        await self.execute_query(query, params)

    async def delete_user(self, telegram_id: int) -> None:
        """Удаление пользователя"""
        await self.execute_query(
            """
            DECLARE $telegram_id AS Uint64;
            DELETE FROM users WHERE telegram_id = $telegram_id;
            """,
            {"$telegram_id": (telegram_id, ydb.PrimitiveType.Uint64)}
        )

    def _row_to_user(self, row) -> User:
        return User(
            telegram_id=row["telegram_id"],
            full_name=row.get("full_name"),
            language_code=row.get("language_code"),
            free_generate=row.get("free_generate"),
            created_at=row.get("created_at")
        )

    def _to_params(self, user: User) -> dict:
        return {
            "$telegram_id": (user.telegram_id, ydb.PrimitiveType.Uint64),
            "$full_name": (user.full_name, ydb.OptionalType(ydb.PrimitiveType.Utf8)),
            "$language_code": (user.language_code, ydb.OptionalType(ydb.PrimitiveType.Utf8)),
            "$free_generate": (user.free_generate, ydb.PrimitiveType.Bool),
            "$created_at": (user.created_at, ydb.OptionalType(ydb.PrimitiveType.Uint64)),
        }


# ---------------------------------------------------------------- КЭШ ----------------------------------------------------------------------


@dataclass
class Cache:
    telegram_id: int = None
    photo_message_id: Optional[int] = None
    file_id: Optional[str] = None
    pay_message_id: Optional[int] = None


class CacheClient(YDBClient):
    def __init__(self, endpoint: str = YDB_ENDPOINT, database: str = YDB_PATH, token: str = YDB_TOKEN):
        super().__init__(endpoint, database, token)
        self.table_name = "cache"
        self.table_schema = """
            CREATE TABLE `cache` (
                `telegram_id` Uint64 NOT NULL,
                `photo_message_id` Int32,
                `file_id` Utf8,
                `pay_message_id` Int32,
                PRIMARY KEY (`telegram_id`, `photo_message_id`)
            )
        """
        
    async def create_cache_table(self):
        """
        Создание таблицы cache
        """
        await self.create_table(self.table_name, self.table_schema)
    
    async def insert_cache(self, cache: Cache) -> Cache:
        """
        Вставка записи в кэш
        """
        await self.execute_query(
            """
            DECLARE $telegram_id AS Uint64;
            DECLARE $photo_message_id AS Int32?;
            DECLARE $file_id AS Utf8?;
            DECLARE $pay_message_id AS Int32?;

            UPSERT INTO cache (telegram_id, photo_message_id, file_id, pay_message_id)
            VALUES ($telegram_id, $photo_message_id, $file_id, $pay_message_id);
            """,
            self._to_params(cache)
        )

    async def get_cache_by_telegram_id(self, telegram_id: int) -> dict[int, dict[str, str]]:
        """
        Получение всех записей кэша для пользователя в виде словаря:
        {photo_message_id: {"photo": file_id, "pay_message_id": pay_message_id}}
        """
        result = await self.execute_query(
            """
            DECLARE $telegram_id AS Uint64;

            SELECT photo_message_id, file_id, pay_message_id
            FROM cache
            WHERE telegram_id = $telegram_id
            ORDER BY photo_message_id;
            """,
            {"$telegram_id": (telegram_id, ydb.PrimitiveType.Uint64)}
        )

        rows = result[0].rows
        return {
            row["photo_message_id"]: {
                "photo": row["file_id"],
                "pay_message_id": row.get("pay_message_id")
            } for row in rows
            }

    async def delete_cache_by_telegram_id(self, telegram_id: int) -> None:
        """
        Удаление всех записей кэша для пользователя
        """
        await self.execute_query(
            """
            DECLARE $telegram_id AS Uint64;
            DELETE FROM cache WHERE telegram_id = $telegram_id;
            """,
            {"$telegram_id": (telegram_id, ydb.PrimitiveType.Uint64)}
        )

    async def delete_cache_by_telegram_id_and_photo_message_id(self, telegram_id: int, photo_message_id: int) -> None:
        """
        Удаление записи кэша по telegram_id и photo_message_id
        """
        await self.execute_query(
            """
            DECLARE $telegram_id AS Uint64;
            DECLARE $photo_message_id AS Int32;
            
            DELETE FROM cache WHERE telegram_id = $telegram_id AND photo_message_id = $photo_message_id;
            """,
            {
                "$telegram_id": (telegram_id, ydb.PrimitiveType.Uint64),
                "$photo_message_id": (photo_message_id, ydb.PrimitiveType.Int32)
            }
        )

    # --- helpers ---
    def _row_to_cache(self, row) -> Cache:
        return Cache(
            telegram_id=row["telegram_id"],
            photo_message_id=row.get("photo_message_id"),
            file_id=row.get("file_id"),
            pay_message_id=row.get("pay_message_id")
        )

    def _to_params(self, cache: Cache) -> dict:
        return {
            "$telegram_id": (cache.telegram_id, ydb.PrimitiveType.Uint64),
            "$photo_message_id": (cache.photo_message_id, ydb.OptionalType(ydb.PrimitiveType.Int32)),
            "$file_id": (cache.file_id, ydb.OptionalType(ydb.PrimitiveType.Utf8)),
            "$pay_message_id": (cache.pay_message_id, ydb.OptionalType(ydb.PrimitiveType.Int32)),
        }


# ------------------------------------------------------------ ПЛАТЕЖИ -----------------------------------------------------------


@dataclass
class Payment:
    telegram_id: int
    message_id: int
    amount: int
    type: PaymentType
    created_at: Optional[int] = None  # Храним как timestamp (секунды с эпохи)


class PaymentClient(YDBClient):
    def __init__(self, endpoint: str = YDB_ENDPOINT, database: str = YDB_PATH, token: str = YDB_TOKEN):
        super().__init__(endpoint, database, token)
        self.table_name = "payments"
        self.table_schema = """
            CREATE TABLE `payments` (
                `telegram_id` Uint64 NOT NULL,
                `message_id` Int32 NOT NULL,
                `amount` Uint16 NOT NULL,
                `type` Utf8 NOT NULL,
                `created_at` Uint64 NOT NULL,
                PRIMARY KEY (`telegram_id`, `message_id`)
            )
        """
    
    async def create_payments_table(self):
        """
        Создание таблицы payments
        """
        await self.create_table(self.table_name, self.table_schema)
    
    async def insert_payment(self, payment: Payment) -> Payment:
        """
        Вставка нового платежа с автогенерацией ID
        """
        
        if payment.created_at is None:
            payment.created_at = int(datetime.now(timezone.utc).timestamp())
        
        await self.execute_query(
            """
            DECLARE $telegram_id AS Uint64;
            DECLARE $message_id AS Int32;
            DECLARE $amount AS Uint16;
            DECLARE $type AS Utf8;
            DECLARE $created_at AS Uint64;

            INSERT INTO payments (telegram_id, message_id, amount, type, created_at)
            VALUES ($telegram_id, $message_id, $amount, $type, $created_at);
            """,
            self._to_params(payment)
        )

    async def delete_payment_by_telegram_and_message_id(self, telegram_id: int, message_id: int) -> None:
        """
        Удаление записи кэша по telegram_id и message_id
        """
        await self.execute_query(
            """
            DECLARE $telegram_id AS Uint64;
            DECLARE $message_id AS Int32;
            DELETE FROM payments WHERE telegram_id = $telegram_id AND message_id = $message_id;
            """,
            {
                "$telegram_id": (telegram_id, ydb.PrimitiveType.Uint64),
                "$message_id": (message_id, ydb.PrimitiveType.Int32)
            }
        )

    # --- helpers ---
    def _row_to_payment(self, row) -> Payment:
        return Payment(
            telegram_id=row["telegram_id"],
            message_id=row["message_id"],
            amount=row["amount"],
            type=row["type"],
            created_at=row["created_at"],
        )
    
    @staticmethod
    def timestamp_to_datetime(timestamp: int) -> datetime:
        """Конвертация timestamp в datetime объект"""
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    
    @staticmethod
    def datetime_to_timestamp(dt: datetime) -> int:
        """Конвертация datetime в timestamp"""
        return int(dt.timestamp())

    def _to_params(self, payment: Payment) -> dict:
        return {
            "$telegram_id": (payment.telegram_id, ydb.PrimitiveType.Uint64),
            "$message_id": (payment.message_id, ydb.PrimitiveType.Int32),
            "$amount": (payment.amount, ydb.PrimitiveType.Uint16),
            "$type": (payment.type, ydb.PrimitiveType.Utf8),
            "$created_at": (payment.created_at, ydb.PrimitiveType.Uint64),
        }


# --------------------------------------------------------- СОЗДАНИЕ ТАБЛИЦ -------------------------------------------------------


async def create_tables_on_ydb():
    # Создание всех таблиц в базе
    async with UserClient() as client:
        await client.create_users_table()
        print("Table 'USERS' created successfully!")

    async with CacheClient() as client:
        await client.create_cache_table()
        print("Table 'CACHE' created successfully!")

    async with PaymentClient() as client:
        await client.create_payments_table()
        print("Table 'PAYMENTS' created successfully!")


# --------------------------------------------------------- ОЧИСТИТЬ ТАБЛИЦЫ -------------------------------------------------------


async def clear_tables_on_ydb():
    async with YDBClient() as client:
        await client.clear_all_tables()
        print("Tables cleared successfully!")


# --------------------------------------------------------- ЗАПУСК -------------------------------------------------------


if __name__ == "__main__":
    asyncio.run(clear_tables_on_ydb())

