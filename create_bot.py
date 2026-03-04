from maxbot import Dispatcher
from maxbot.api import MaxBot
from maxbot.fsm import State, StatesGroup, SQLiteStorage
from PIL import Image
from PIL import ImageEnhance
import io
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

TOKEN = os.getenv('MAX_BOT_TOKEN') or os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("MAX_BOT_TOKEN (или BOT_TOKEN) не найден в переменных окружения. Проверьте файл .env")

FSM_STORAGE_DB = os.getenv('FSM_STORAGE_DB', 'fsm_storage_db.sqlite')
storage = SQLiteStorage(FSM_STORAGE_DB)

# Настройка прокси (если указан)
PROXY_URL = os.getenv('PROXY_URL')  # Формат: http://user:pass@host:port или socks5://user:pass@host:port

API_BASE_URL = os.getenv('MAX_API_BASE_URL', 'https://platform-api.max.ru')
API_VERSION = os.getenv('MAX_API_VERSION')
USE_QUERY_TOKEN = os.getenv('MAX_USE_QUERY_TOKEN', '').lower() in ('1', 'true', 'yes')
SSL_VERIFY = os.getenv('MAX_SSL_VERIFY', '').lower() not in ('0', 'false', 'no')
FORCE_USER_ID = os.getenv('MAX_FORCE_USER_ID', '').lower() not in ('0', 'false', 'no')

bot = MaxBot(
    token=TOKEN,
    base_url=API_BASE_URL,
    api_version=API_VERSION,
    proxy_url=PROXY_URL,
    use_query_token=USE_QUERY_TOKEN,
    ssl_verify=SSL_VERIFY,
    force_user_id=FORCE_USER_ID
)
proxy_display = PROXY_URL.split('@')[-1] if PROXY_URL and '@' in PROXY_URL else PROXY_URL
if PROXY_URL:
    print(f"✅ Бот инициализирован с прокси: {proxy_display}")
else:
    print("ℹ️ Бот инициализирован без прокси. Если возникают проблемы с подключением, настройте PROXY_URL в .env")

dp = Dispatcher(storage=storage)

# Получаем ID администратора из переменных окружения
admin_id_str = os.getenv('ADMIN_ID')
if not admin_id_str:
    raise ValueError("ADMIN_ID не найден в переменных окружения. Проверьте файл .env")

# Преобразуем ADMIN_ID в правильный формат (поддерживает список через запятую)
admin_id = {}
admin_items = [item.strip() for item in admin_id_str.split(',') if item.strip()]
for item in admin_items:
    try:
        admin_id_int = int(item)
        admin_id[str(admin_id_int)] = "admin"
    except ValueError:
        admin_id[item] = "admin"

print(f"✅ ADMIN_ID установлен: {', '.join(admin_id.keys())}")


class ProfileStatesGroup(StatesGroup):
    vibor_pay_or_back = State()
    menu_start = State()
    categories = State()
    tovar = State()
    insaid_tovar = State()
    tea_weight = State()
    count_insaid_tovar = State()
    basket_menu = State()
    delete_product_one = State()
    pay_cart = State()
    pay_cart_CDEK = State()
    payment_confirmation = State()
    pay = State()
    pay_cart_many_address_CDEK = State()
    pay_cart_many_address = State()
    checking = State()
    addressUSER = State()
    address_processing = State()
    address_processing_CDEK = State()
    address_processing_BCE = State()
    pay_cart_BCE = State()
    zabrat_iz_magaziana = State()
    cancel_order_reason = State()

    name = State()
    price = State()
    weight = State()
    photo = State()


# Код Сбера
async def photo():
    with Image.open('images/image_2026-01-01_15-47-02.png') as img:
        img_resized = img.resize((330, 330))
        enhancer = ImageEnhance.Sharpness(img_resized)
        img_sharpened = enhancer.enhance(2.0)

    # Сохраняем измененное изображение в байтовый поток
    output_code = io.BytesIO()
    img_sharpened.save(output_code, format='PNG')
    output_code.seek(0)
    return output_code
