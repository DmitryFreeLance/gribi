# Настройка переменных окружения

Проект использует переменные окружения для хранения конфиденциальных данных и настроек.

## Шаг 1: Установка зависимостей

Убедитесь, что установлен пакет `python-dotenv`:

```bash
pip install -r requirements.txt
```

## Шаг 2: Создание .env файла

Создайте файл `.env` в корне проекта на основе `.env.example`:

```bash
cp .env.example .env
```

Или создайте файл `.env` вручную со следующим содержимым:

```env
# Max Bot Configuration
MAX_BOT_TOKEN=your_max_bot_token_here
MAX_API_BASE_URL=https://platform-api.max.ru
# MAX_USE_QUERY_TOKEN=1
# MAX_SSL_VERIFY=0
# MAX_FORCE_USER_ID=1
# MAX_API_VERSION=your_api_version_if_needed
MAX_GROUP_ID=your_max_group_chat_id_here
ADMIN_ID=your_admin_id_here

# Payment Configuration
OZON_CARD_NUMBER=2204 2402 4392 8589

# Contact Information
CONSULTANT_TELEGRAM=https://t.me/Dina_Ildarovna
WEBSITE_URL=https://aivedi.ru

# Shop Information
SHOP_ADDRESS=Менделеева 171/3
SHOP_PHONE=89874974987
SHOP_HOURS=11:00-19:00

# Database Configuration
DATABASE_NAME=sqlite_python.db
FSM_STORAGE_DB=fsm_storage_db.sqlite
# DEFAULT_DB_PATH=sqlite_python.db

# Delivery Prices
DELIVERY_YANDEX_PRICE=250
DELIVERY_CDEK_PRICE=300
```

## Шаг 3: Заполнение значений

Замените значения в `.env` файле на реальные:

- `MAX_BOT_TOKEN` - токен вашего бота в мессенджере Max
- `MAX_API_BASE_URL` - базовый URL Max Bot API (если используете другой домен)
- `MAX_USE_QUERY_TOKEN` - включить передачу токена через query-параметр (для старого botapi домена)
- `MAX_SSL_VERIFY` - отключить проверку SSL (только если у вас корпоративный прокси с подменой сертификата)
- `MAX_FORCE_USER_ID` - отправлять личные сообщения через user_id даже если передан chat_id
- `MAX_GROUP_ID` - ID группы в Max (для команды /post)
- `ADMIN_ID` - ваш ID в Max (можно несколько через запятую)
- `DEFAULT_DB_PATH` - путь к шаблонной БД для первичной инициализации (если DATABASE_NAME отсутствует)
- Остальные значения настройте по необходимости

## Важно!

- **НЕ коммитьте** файл `.env` в репозиторий (он должен быть в `.gitignore`)
- Файл `.env.example` можно коммитить - это шаблон без конфиденциальных данных




