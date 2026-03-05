from maxbot.markdown import hbold
import sqlite3
import io
from PIL import Image
from PIL import ImageEnhance
import asyncio
import sys
import os
from dotenv import load_dotenv
import re
from maxbot.fsm import FSMContext, StorageKey
from maxbot import types, Dispatcher, Router, F
from maxbot.filters import Command, CommandStart
from ui import inline_menu
from constant import emojis_to_topics, add_to_basket, get_basket_for_user, get_basket_info_product, \
    delete_basket_for_user, delete_product_for_user, add_to_address, get_address_for_user, search_address_in_user, \
    search_address_in_user_BCE, search_BCE, get_basket_info_all, create_database_accurately, get_database_accurately, \
    add_order_accurately, clear_basket, get_basket_info_product_by_id, create_order, get_order_by_id, update_order_status, ensure_database

from create_bot import photo

# from handlers.add_product import register_handlers_product
# from handlers.delete_product import delete_handlers_product
# from handlers.edit_product import edit_handlers_product
from handlers.dont_repeat_yourself import categories, show_basket, send_order_to_admins

from create_bot import bot, dp, ProfileStatesGroup, admin_id
from maxbot.types import FSInputFile, URLInputFile, BufferedInputFile

# Загружаем переменные окружения
load_dotenv()

# Получаем переменные из .env
DATABASE_NAME = os.getenv('DATABASE_NAME', 'sqlite_python.db')
OZON_CARD_NUMBER = os.getenv('OZON_CARD_NUMBER', '2204 2402 4392 8589')
CONSULTANT_TELEGRAM = os.getenv('CONSULTANT_TELEGRAM', 'https://t.me/Dina_Ildarovna')
WEBSITE_URL = os.getenv('WEBSITE_URL', 'https://aivedi.ru')
SHOP_ADDRESS = os.getenv('SHOP_ADDRESS', 'Менделеева 171/3')
SHOP_PHONE = os.getenv('SHOP_PHONE', '89874974987')
SHOP_HOURS = os.getenv('SHOP_HOURS', '11:00-19:00')
DELIVERY_YANDEX_PRICE = int(os.getenv('DELIVERY_YANDEX_PRICE', '250'))
DELIVERY_CDEK_PRICE = int(os.getenv('DELIVERY_CDEK_PRICE', '300'))
MAX_GROUP_ID = os.getenv('MAX_GROUP_ID') or os.getenv('GROUP_ID')
try:
    MAX_GROUP_ID = int(MAX_GROUP_ID) if MAX_GROUP_ID else None
except ValueError:
    MAX_GROUP_ID = None
global name
global address
global address_CDEK
global address_BCE

# register_handlers_product(dp)
# delete_handlers_product(dp)
# edit_handlers_product(dp)
#291

form_router = Router()


async def show_product_card(message: types.Message, state: FSMContext, record, display_name: str = None):
    product_id = record[0]
    actual_name = record[1]
    if display_name is None:
        display_name = actual_name

    await state.update_data(product_id=product_id, product_name=actual_name)

    # Проверяем текущее количество товара в корзине
    user_products = await get_basket_for_user(message.from_user.id)
    current_count = 0
    for prod_id, _, count in user_products:
        if prod_id == product_id:
            current_count = count
            break

    # Создаем inline кнопки
    inline_kb = [
        [
            types.InlineKeyboardButton(text="➖", callback_data=f"decrease_{product_id}"),
            types.InlineKeyboardButton(text=f"Колич.: {current_count}", callback_data="count_display"),
            types.InlineKeyboardButton(text="➕", callback_data=f"increase_{product_id}")
        ],
        [types.InlineKeyboardButton(text="📝 Ввести количество", callback_data=f"input_count_{product_id}")],
        [types.InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_categories")]
    ]
    inline_keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_kb)

    filename_photo = record[5]
    default_image = 'images/image_2026-01-01_15-47-02.png'
    if filename_photo and os.path.exists(filename_photo):
        image_path = filename_photo
    elif os.path.exists(default_image):
        image_path = default_image
    else:
        image_path = None

    if image_path:
        with Image.open(image_path) as img:
            img_resized = img.resize((330, 330))
            enhancer = ImageEnhance.Sharpness(img_resized)
            img_sharpened = enhancer.enhance(2.0)

        output = io.BytesIO()
        img_sharpened.save(output, format='PNG')
        output.seek(0)
    else:
        output = None

    description = record[6] if record[6] is not None else ''
    max_caption_length = 1024
    base_caption = (
        f"<b>Вы выбрали товар: {display_name}\n\n</b>"
        f"<b>Дополнительная информация о товаре:\n</b>"
        f"<b>Вес:</b> <code>{record[2]}⚖\n</code>"
        f"<b>Цена:</b> <code>{record[3]}💵\n</code>"
        f"<b>Полное описание можете посмотреть тут:</b>\n{WEBSITE_URL}\n"
        f"<b>Описание:</b> "
    )
    remaining_length = max_caption_length - len(base_caption)
    if len(description) > remaining_length:
        description = description[:remaining_length - 3] + "..."
    caption = f"{base_caption}{description}"

    if output:
        await message.answer_photo(
            BufferedInputFile(
                output.read(),
                filename=filename_photo or 'product.png',
            ),
            caption=caption,
            parse_mode='HTML',
            reply_markup=inline_keyboard
        )
    else:
        await message.answer(
            caption,
            parse_mode='HTML',
            reply_markup=inline_keyboard
        )


def parse_post_buttons(text: str):
    buttons = []
    errors = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if " - " not in line:
            errors.append(raw_line)
            continue
        name, url = line.split(" - ", 1)
        name = name.strip()
        url = url.strip()
        if not name or not url:
            errors.append(raw_line)
            continue
        buttons.append({"text": name, "url": url})
    return buttons, errors


def build_link_keyboard(buttons):
    rows = []
    for btn in buttons:
        rows.append([types.InlineKeyboardButton(text=btn["text"], url=btn["url"])])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


async def publish_post_from_state(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = data.get("post_text")
    buttons = data.get("post_buttons") or []

    if not text:
        await message.answer("Текст поста не задан. Используйте /post заново.")
        await state.clear()
        return
    if not MAX_GROUP_ID:
        await message.answer("MAX_GROUP_ID не задан в .env. Укажите ID группы и попробуйте снова.")
        await state.clear()
        return

    reply_markup = build_link_keyboard(buttons) if buttons else None
    await bot.send_message(chat_id=MAX_GROUP_ID, text=text, reply_markup=reply_markup)
    await message.answer("✅ Пост опубликован в группу.")
    await state.clear()


# старт
@form_router.message(CommandStart())
async def command_start_handler(message: types.Message, state: FSMContext) -> None:
    print(f"USER_ID: {message.from_user.id} USERNAME: {message.from_user.username}")
    kb = [[types.KeyboardButton(text="📃 Выбрать товар"), types.KeyboardButton(text="📲 Консультация")]]
    keyboard = inline_menu(kb)
    await message.answer(f"Здравствуй, {hbold(message.from_user.full_name)}!\n\n<i>Выберите действие</i>", parse_mode='html', reply_markup=keyboard)
    await state.set_state(ProfileStatesGroup.menu_start)


@form_router.message(Command(commands=["post"]))
async def post_start_handler(message: types.Message, state: FSMContext) -> None:
    if str(message.from_user.id) not in admin_id:
        await message.answer("Доступ только для администратора.")
        return
    await state.clear()
    await message.answer("Введите текст поста для публикации в группу Max:")
    await state.set_state(ProfileStatesGroup.post_text)


@form_router.message(ProfileStatesGroup.post_text)
async def post_text_handler(message: types.Message, state: FSMContext) -> None:
    if str(message.from_user.id) not in admin_id:
        await message.answer("Доступ только для администратора.")
        await state.clear()
        return
    await state.update_data(post_text=message.text, post_buttons=[])
    inline_kb = [[types.InlineKeyboardButton(text="✅ Готово", callback_data="post_done")]]
    inline_keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_kb)
    await message.answer(
        'Теперь отправьте кнопки в формате: "НАЗВАНИЕ - ССЫЛКА"\n'
        'Можно несколько строк в одном сообщении.\n\n'
        'Когда закончите — нажмите "Готово".',
        reply_markup=inline_keyboard
    )
    await state.set_state(ProfileStatesGroup.post_buttons)


@form_router.message(ProfileStatesGroup.post_buttons)
async def post_buttons_handler(message: types.Message, state: FSMContext) -> None:
    if str(message.from_user.id) not in admin_id:
        await message.answer("Доступ только для администратора.")
        await state.clear()
        return
    if isinstance(message.text, str) and message.text.strip().lower() == "готово":
        await publish_post_from_state(message, state)
        return
    buttons, errors = parse_post_buttons(message.text or "")
    data = await state.get_data()
    existing = data.get("post_buttons") or []
    if buttons:
        existing.extend(buttons)
        await state.update_data(post_buttons=existing)
    inline_kb = [[types.InlineKeyboardButton(text="✅ Готово", callback_data="post_done")]]
    inline_keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_kb)
    if buttons:
        msg = f"Добавлено кнопок: {len(buttons)}.\n"
    else:
        msg = "Кнопки не распознаны.\n"
    if errors:
        msg += "Не удалось разобрать строки:\n" + "\n".join(errors) + "\n"
    msg += 'Пришлите следующую кнопку в формате: "НАЗВАНИЕ - ССЫЛКА"\nили нажмите "Готово".'
    await message.answer(msg, reply_markup=inline_keyboard)


@form_router.callback_query(F.data == "post_done")
async def post_done_callback(callback: types.CallbackQuery, state: FSMContext) -> None:
    if str(callback.from_user.id) not in admin_id:
        await callback.answer("Доступ только для администратора.", show_alert=True)
        return
    await publish_post_from_state(callback.message, state)
    await callback.answer("Опубликовано")


@form_router.message(Command(commands=["checking"]))
async def command_start_handler(message: types.Message, state: FSMContext) -> None:
    if str(message.chat.id) in admin_id:  # Изменить id пользователя на её
        kb = [
            [types.KeyboardButton(text="История заказов")],
        ]
        keyboard = inline_menu(kb)
        all_orders = await get_basket_info_all()
        formatted_message = "Список заказов:\n\n"
        for order in all_orders:
            formatted_message += f"ID заказа: {order[0]}, ID: {order[1]}, Количество: {order[2]}, Наименование: {order[3]}\n\n"

        # Отправляем отформатированное сообщение
        await bot.send_message(message.chat.id, text=formatted_message)

        await bot.send_message(message.chat.id,
                               text="Чтобы подтвердить заказ, введите номер и Yes/No\n\nПример:\n6542790529 Yes\n6542790529 No",
                               reply_markup=keyboard)

        await state.set_state(ProfileStatesGroup.checking)
    else:
        kb = [[types.KeyboardButton(text="📃 Выбрать товар"), types.KeyboardButton(text="📲 Консультация")]]

        keyboard = inline_menu(kb)
        await message.answer(f"Здравствуй, {hbold(message.from_user.full_name)}!\n\n<i>Выберите действие</i>",
                               parse_mode='html',
                               reply_markup=keyboard,
                               )
        # передаем в ожидание ответа от первого меню при старте
        await state.set_state(ProfileStatesGroup.menu_start)


# ловим ответ от стартового меню
@form_router.message(ProfileStatesGroup.menu_start)
async def load_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(
        address='',
        address_CDEK='',
        address_BCE='',
        name=message.text,
    )
    data = await state.get_data()
    if message.text == '📃 Выбрать товар':
        await categories(message, answer_text="<b>Выберите категорию</b>")
        await state.set_state(ProfileStatesGroup.categories)

    elif message.text == '📲 Консультация':
        formatted_message = f"<b>Вопросы по поводу вашего заказа (даты доставки и тд.) можете задать: {CONSULTANT_TELEGRAM}\n</b>"
        await message.answer(text=formatted_message, parse_mode='html')

    elif message.text == 'Мои заказы':
        formatted_message = f"Вопросы по поводу вашего заказа (даты доставки и тд.) можете задать: {CONSULTANT_TELEGRAM}\n\nВаши заказы:\n"
        result_orders = await get_database_accurately(message.chat.id)

        if result_orders == 'Product not found':
            await message.answer(text="У вас пока нет заказов.")
        else:
            for order in result_orders:
                formatted_message += f"ID заказа: {order[0]}\nID: {order[1]}\nКоличество: {order[2]}\nСостояние: {'Подтвержден' if order[3] else 'Не подтвержден'}\n\n"

            await message.answer(text=formatted_message)
    elif message.text == 'Выйти':
        await message.answer(text="Вы вышли из меню.")


# Ловим ответ на checking
@form_router.message(ProfileStatesGroup.checking)
async def checking(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    data = await state.get_data()
    if message.text != 'Выйти':
        if message.text == "История заказов":
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()

            # Выполнение запроса
            cursor.execute('SELECT * FROM accurately_products')
            data = cursor.fetchall()
            for i in data:
                await bot.send_message(message.chat.id, text=f"{i[0]}) ID: {i[1]}, Кол-во: {i[2]}, Товар: {i[3]}\n\n")
        else:
            number_and_app = message.text.split(" ")
            id_user = number_and_app[0]
            Yes_and_No = number_and_app[1]

            user_products = await get_basket_for_user(int(id_user))
            korzina = []

            for i, (product_id, product, count) in enumerate(user_products, 1):
                products_str = f"{i}) {product} {count} шт\n"
                product_info = await get_basket_info_product_by_id(product_id)
                if not product_info or len(product_info) == 0:
                    korzina.append(f"{products_str}Товар: {product}, Количество: {count} шт")
                    continue
                price = int(str(product_info[0][3]).replace("₽", "")) * count
                korzina.append(f"{products_str}Цена: {price}💵Вес: {product_info[0][2]}⚖")

            korzina_str = "\n".join(korzina)

            if Yes_and_No == 'No':  # Отправляем уведомление, что деньги не поступили на счет
                await bot.send_message(user_id=int(number_and_app[0]), text=f"<b>Ваш заказ\n\nНЕ ПОДТВЕРЖДЕН</b>", parse_mode='html')
            elif Yes_and_No == 'Yes':  # Отправляем уведомление, что деньги поступили на счет
                await bot.send_message(user_id=int(number_and_app[0]), text=f"<b>Ваш заказ\n\nПОДТВЕРЖДЕН</b>", parse_mode='html')

                for product_id, product, count in user_products:
                    await add_order_accurately(ID_client=id_user, count=count, product=product, accurately=True)

                await delete_basket_for_user(id_user)
    else:
        kb = [[types.KeyboardButton(text="📃 Выбрать товар"), types.KeyboardButton(text="📲 Консультация")]]

        keyboard = inline_menu(kb)
        await bot.send_message(message.chat.id,
                               f"Здравствуй, {hbold(message.from_user.full_name)}!\n\n<i>Выберите действие</i>",
                               parse_mode='html',
                               reply_markup=keyboard,
                               )
        # передаем в ожидание ответа от первого меню при старте
        await state.set_state(ProfileStatesGroup.menu_start)


# Ловим ответ от кнопки "выбрать товар"
@form_router.message(ProfileStatesGroup.categories)
async def load_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    data = await state.get_data()
    if str(message.text) in emojis_to_topics:
        topic = emojis_to_topics[message.text]  # Получаем название товара из словаря

        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()
        cursor.execute(f"SELECT * FROM list_gribs WHERE topic=?", (topic,))
        records = cursor.fetchall()
        await state.update_data(current_topic=topic)

        kb = []
        if topic == "Чай":
            items = [record[1] for record in records]
            chunk_size = 21
            chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
            first = True
            for chunk in chunks:
                kb = [[types.KeyboardButton(text=item)] for item in chunk]
                keyboard = inline_menu(kb)
                if first:
                    await message.answer(
                        f"<b>🧷 Добро пожаловать в раздел: {message.text}\n\n</b>"
                        "<i>Выберите товар из списка ниже.</i>",
                        reply_markup=keyboard,
                        parse_mode='html'
                    )
                    first = False
                else:
                    await message.answer(
                        "<i>Продолжение списка товаров:</i>",
                        reply_markup=keyboard,
                        parse_mode='html'
                    )
            nav_kb = [
                [types.KeyboardButton(text="Назад ⬅")],
                [types.KeyboardButton(text="📦 Корзина")],
            ]
            nav_keyboard = inline_menu(nav_kb)
            await message.answer(
                "<i>Навигация:</i>",
                reply_markup=nav_keyboard,
                parse_mode='html'
            )
            await state.set_state(ProfileStatesGroup.tovar)
            return
        else:
            single_row_topics = {"Шляпки", "Капуслы", "Молотые"}
            if topic in single_row_topics:
                items = [record[1] for record in records]
                chunk_size = 21
                chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
                first = True
                for chunk in chunks:
                    kb = [[types.KeyboardButton(text=item)] for item in chunk]
                    keyboard = inline_menu(kb)
                    if first:
                        await message.answer(
                            f"<b>🧷 Добро пожаловать в раздел: {message.text}\n\n</b>"
                            "<i>📑 Чтобы добавить товар в корзину, просто нажмите на него и проследуйте инструкции.\n\n</i>",
                            reply_markup=keyboard,
                            parse_mode='html'
                        )
                        first = False
                    else:
                        await message.answer(
                            "<i>Продолжение списка товаров:</i>",
                            reply_markup=keyboard,
                            parse_mode='html'
                        )
                nav_kb = [
                    [types.KeyboardButton(text="Назад ⬅")],
                    [types.KeyboardButton(text="📦 Корзина")],
                ]
                nav_keyboard = inline_menu(nav_kb)
                await message.answer(
                    "<i>Навигация:</i>",
                    reply_markup=nav_keyboard,
                    parse_mode='html'
                )
                await state.set_state(ProfileStatesGroup.tovar)
                return
            kb = [
                [types.KeyboardButton(text="Назад ⬅")],
                [types.KeyboardButton(text="📦 Корзина")],
            ]
            for i in range(0, len(records), 2):
                record_current = records[i][1]
                if i + 1 < len(records):  # Проверяем, что следующая запись существует
                    record_next = records[i + 1][1]
                    kb.append([types.KeyboardButton(text=f"{record_current}"),
                               types.KeyboardButton(text=f"{record_next}")])
                else:
                    kb.append([types.KeyboardButton(text=f"{record_current}")])

        keyboard = inline_menu(kb)
        await message.answer(
            f"<b>🧷 Добро пожаловать в раздел: {message.text}\n\n</b>"
            "<i>📑 Чтобы добавить товар в корзину, просто нажмите на него и проследуйте инструкции.\n\n</i>",
            reply_markup=keyboard,
            parse_mode='html'
        )
        await state.set_state(ProfileStatesGroup.tovar)

    elif str(message.text) == 'Вернутся на главную ⬅':
        kb = [[types.KeyboardButton(text="📃 Выбрать товар"), types.KeyboardButton(text="📲 Консультация")]]

        keyboard = inline_menu(kb)
        await bot.send_message(message.chat.id,
                               f"Выберите действие",
                               parse_mode='html',
                               reply_markup=keyboard,
                               )
        # передаем в ожидание ответа от первого меня при старте
        await state.set_state(ProfileStatesGroup.menu_start)


    elif str(message.text) == '📦 Корзина':
        await show_basket(message, state)


# Ловим ответ от кнопки категорий
@form_router.message(ProfileStatesGroup.tovar)
async def load_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    data = await state.get_data()

    if str(message.text) == 'Назад ⬅':
        await categories(message, answer_text="<b>Выберите категорию</b>")
        await state.set_state(ProfileStatesGroup.categories)

    elif message.text == "📦 Корзина":
        await show_basket(message, state)
    else:
        global name
        display_name = message.text
        name = display_name
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()
        cursor.execute("SELECT * FROM list_gribs WHERE name=? ORDER BY id", (display_name,))
        records = cursor.fetchall()
        sqlite_connection.close()
        if len(records) > 0:
            await show_product_card(message, state, records[0], display_name=display_name)
            await state.set_state(ProfileStatesGroup.insaid_tovar)




# Обработчик inline кнопок для изменения количества товара
@form_router.callback_query(F.data.startswith("increase_"))
async def increase_product_count(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    product_name = data.get('product_name', '')
    
    # Получаем информацию о товаре
    product_info = await get_basket_info_product_by_id(product_id)
    if not product_info or len(product_info) == 0:
        await callback.answer("Товар не найден", show_alert=True)
        return
    
    product_name = product_info[0][1]  # Название товара из базы
    
    # Добавляем товар в корзину (функция сама обновит количество если товар уже есть)
    await add_to_basket(user_id=callback.from_user.id, product_id=product_id, product=product_name, counnt=1)
    
    # Получаем обновленное количество
    user_products = await get_basket_for_user(callback.from_user.id)
    current_count = 0
    for prod_id, prod_name, count in user_products:
        if prod_id == product_id:
            current_count = count
            break
    
    # Обновляем кнопки
    inline_kb = [
        [
            types.InlineKeyboardButton(text="➖", callback_data=f"decrease_{product_id}"),
            types.InlineKeyboardButton(text=f"Колич.: {current_count}", callback_data="count_display"),
            types.InlineKeyboardButton(text="➕", callback_data=f"increase_{product_id}")
        ],
        [types.InlineKeyboardButton(text="📝 Ввести количество", callback_data=f"input_count_{product_id}")],
        [types.InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_categories")]
    ]
    inline_keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_kb)
    
    try:
        await callback.message.edit_reply_markup(reply_markup=inline_keyboard)
        await callback.answer(f"Добавлено! Количество: {current_count}")
    except Exception as e:
        error_msg = str(e).lower()
        # Игнорируем ошибку "message is not modified" - это означает, что сообщение уже актуально
        if "message is not modified" in error_msg or "not modified" in error_msg:
            await callback.answer(f"Количество: {current_count}")
        else:
            await callback.answer("Обновлено!")
            print(f"Ошибка при обновлении кнопок (increase): {e}")


@form_router.callback_query(F.data.startswith("decrease_"))
async def decrease_product_count(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    
    # Получаем текущее количество
    user_products = await get_basket_for_user(callback.from_user.id)
    current_count = 0
    for prod_id, prod_name, count in user_products:
        if prod_id == product_id:
            current_count = count
            break
    
    if current_count <= 0:
        await callback.answer("Товар отсутствует в корзине", show_alert=True)
        return
    
    # Уменьшаем количество на 1
    await delete_product_for_user(user_id=callback.from_user.id, product_id=product_id, counnt=1)
    
    # Получаем обновленное количество
    user_products = await get_basket_for_user(callback.from_user.id)
    new_count = 0
    for prod_id, prod_name, count in user_products:
        if prod_id == product_id:
            new_count = count
            break
    
    # Обновляем кнопки
    inline_kb = [
        [
            types.InlineKeyboardButton(text="➖", callback_data=f"decrease_{product_id}"),
            types.InlineKeyboardButton(text=f"Колич.: {new_count}", callback_data="count_display"),
            types.InlineKeyboardButton(text="➕", callback_data=f"increase_{product_id}")
        ],
        [types.InlineKeyboardButton(text="📝 Ввести количество", callback_data=f"input_count_{product_id}")],
        [types.InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_categories")]
    ]
    inline_keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_kb)
    
    try:
        await callback.message.edit_reply_markup(reply_markup=inline_keyboard)
        if new_count > 0:
            await callback.answer(f"Уменьшено! Количество: {new_count}")
        else:
            await callback.answer("Товар удален из корзины")
    except Exception as e:
        error_msg = str(e).lower()
        # Игнорируем ошибку "message is not modified" - это означает, что сообщение уже актуально
        if "message is not modified" in error_msg or "not modified" in error_msg:
            if new_count > 0:
                await callback.answer(f"Количество: {new_count}")
            else:
                await callback.answer("Товар удален из корзины")
        else:
            await callback.answer("Обновлено!")
            print(f"Ошибка при обновлении кнопок (decrease): {e}")


@form_router.callback_query(F.data.startswith("input_count_"))
async def input_product_count(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[2])
    await state.update_data(product_id=product_id)
    
    kb = [[types.KeyboardButton(text="Главное меню ⬅")],
          [types.KeyboardButton(text="1"), types.KeyboardButton(text="2"), types.KeyboardButton(text="3")],
          [types.KeyboardButton(text="4"), types.KeyboardButton(text="5"), types.KeyboardButton(text="6")],
          [types.KeyboardButton(text="7"), types.KeyboardButton(text="8"), types.KeyboardButton(text="9")],
          [types.KeyboardButton(text="10")]]
    keyboard = inline_menu(kb)
    
    await callback.message.answer("<b>Введите количество товара:</b>", reply_markup=keyboard, parse_mode='html')
    await callback.answer()
    await state.set_state(ProfileStatesGroup.count_insaid_tovar)


@form_router.callback_query(F.data == "back_to_categories")
async def back_to_categories_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await categories(callback.message, answer_text="<b>Выберите категорию</b>")
    await state.set_state(ProfileStatesGroup.categories)
    await callback.answer()


@form_router.callback_query(F.data.startswith("remove_from_basket_"))
async def remove_from_basket_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик удаления товара из корзины через inline кнопку"""
    product_id = int(callback.data.split("_")[3])
    
    # Получаем информацию о товаре для отображения
    product_info = await get_basket_info_product_by_id(product_id)
    product_name = "Товар"
    if product_info and len(product_info) > 0:
        product_name = product_info[0][1]
    
    # Получаем текущее количество товара в корзине
    user_products = await get_basket_for_user(callback.from_user.id)
    current_count = 0
    for prod_id, prod_name, count in user_products:
        if prod_id == product_id:
            current_count = count
            break
    
    if current_count > 0:
        # Удаляем товар полностью из корзины
        await delete_product_for_user(callback.from_user.id, product_id, current_count)
        await callback.answer(f"Товар '{product_name}' удален из корзины")
        
        # Удаляем сообщение с товаром
        try:
            await callback.message.delete()
        except:
            pass
        
        # Проверяем, остались ли товары в корзине (прямой запрос к БД для надежности)
        import sqlite3
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM basket WHERE user_id=? AND product_id IS NOT NULL", (callback.from_user.id,))
        remaining_count = cursor.fetchone()[0]
        conn.close()
        
        if remaining_count > 0:
            # Получаем товары через функцию
            user_products = await get_basket_for_user(callback.from_user.id)
            if len(user_products) > 0:
                # Обновляем корзину - показываем обновленный список
                from handlers.dont_repeat_yourself import show_basket
                
                # Создаем объект-обертку для message, чтобы show_basket мог работать
                class TempMessage:
                    def __init__(self, user_id, bot_instance):
                        self.from_user = type('User', (), {'id': user_id})()
                        self.chat = type('Chat', (), {'id': user_id})()
                        self._bot = bot_instance
                        self._user_id = user_id
                    
                    async def answer(self, text=None, **kwargs):
                        if text is None and 'text' in kwargs:
                            text = kwargs.pop('text')
                        await self._bot.send_message(self._user_id, text, **kwargs)
                
                temp_msg = TempMessage(callback.from_user.id, bot)
                await show_basket(temp_msg, state)
        else:
            # Корзина пуста
            from handlers.dont_repeat_yourself import categories
            await bot.send_message(callback.from_user.id, "<code>Корзина пуста</code>", parse_mode='html')
            # Создаем временное сообщение для categories
            class TempMessageForCategories:
                def __init__(self, user_id, bot_instance):
                    self.from_user = type('User', (), {'id': user_id})()
                    self.chat = type('Chat', (), {'id': user_id})()
                    self._bot = bot_instance
                    self._user_id = user_id
                
                async def answer(self, text=None, **kwargs):
                    if text is None:
                        # Если text не передан, берем из kwargs
                        text = kwargs.pop('text', '')
                    await self._bot.send_message(self._user_id, text, **kwargs)
            
            temp_msg = TempMessageForCategories(callback.from_user.id, bot)
            await categories(temp_msg, answer_text="<b>Выберите категорию</b>")
            await state.set_state(ProfileStatesGroup.categories)
    else:
        await callback.answer("Товар не найден в корзине", show_alert=True)


# Обработчик подтверждения заказа
@form_router.callback_query(F.data.startswith("confirm_order_"))
async def confirm_order_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик подтверждения заказа"""
    order_id_str = callback.data.split("_")[2]
    
    # Преобразуем order_id в int (убираем # если есть)
    try:
        order_id = int(order_id_str.replace("#", ""))
    except ValueError:
        # Если не число, пытаемся извлечь user_id из старого формата
        try:
            user_id = int(order_id_str.split("_")[0])
            order_id = None
        except (ValueError, IndexError):
            user_id = None
            order_id = None
            print(f"Не удалось извлечь order_id или user_id: {order_id_str}")
    
    # Получаем информацию о заказе из БД
    user_id = None
    if order_id:
        order_info = await get_order_by_id(order_id)
        if order_info:
            user_id = order_info[1]  # user_id находится во второй колонке
            # Обновляем статус заказа
            from datetime import datetime
            await update_order_status(order_id, 'confirmed', confirmed_at=datetime.now())
        else:
            # Если заказ не найден в БД, пытаемся извлечь user_id из старого формата
            try:
                user_id = int(order_id_str.split("_")[0])
            except:
                pass
    
    # Отправляем сообщение пользователю о подтверждении заказа
    if user_id:
        try:
            order_id_display = f"#{order_id}" if isinstance(order_id, int) else order_id_str
            await bot.send_message(
                user_id=user_id,
                text=(
                    f"✅ <b>Ваш заказ подтвержден!</b>\n\n"
                    f"🆔 ID заказа: <code>{order_id_display}</code>\n\n"
                    f"Спасибо за ваш заказ! Мы свяжемся с вами в ближайшее время.\n\n"
                    f"Обычно это занимает около 1-3 часов."
                ),
                parse_mode='HTML'
            )
            print(f"✅ Сообщение о подтверждении отправлено пользователю {user_id}")
        except Exception as user_error:
            print(f"❌ Не удалось отправить сообщение пользователю {user_id}: {user_error}")
    
    # Обновляем сообщение у администратора
    try:
        # Получаем оригинальный текст сообщения
        original_text = callback.message.text or (callback.message.html_text if hasattr(callback.message, 'html_text') else "")
        
        # Добавляем информацию о подтверждении (только если еще не добавлено)
        if "ЗАКАЗ ПОДТВЕРЖДЕН" not in original_text.upper():
            updated_text = original_text + "\n\n✅ <b>ЗАКАЗ ПОДТВЕРЖДЕН</b>\n"
            updated_text += f"👤 Подтвердил: @{callback.from_user.username if callback.from_user.username else 'не указан'}"
            
            try:
                await callback.message.edit_text(
                    updated_text,
                    parse_mode='HTML'
                )
            except Exception as edit_error:
                # Если не удалось обновить текст, просто убираем кнопки
                print(f"Не удалось обновить текст сообщения: {edit_error}")
        
        # Убираем кнопки
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception as markup_error:
            # Игнорируем ошибку, если кнопок уже нет
            pass
        
        await callback.answer("Заказ подтвержден!", show_alert=True)
        
    except Exception as e:
        print(f"Ошибка при обновлении сообщения у администратора: {e}")
        await callback.answer("Заказ подтвержден! Пользователю отправлено уведомление.", show_alert=True)


# Обработчик отмены заказа
@form_router.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик отмены заказа - отправляет админу в ЛС запрос на причину"""
    order_id_str = callback.data.split("_")[2]
    
    # Преобразуем order_id в int (убираем # если есть)
    try:
        order_id = int(order_id_str.replace("#", ""))
    except ValueError:
        # Если не число, оставляем как строку (старый формат)
        order_id = order_id_str
    
    # Получаем информацию о заказе из БД
    user_id = None
    if isinstance(order_id, int):
        order_info = await get_order_by_id(order_id)
        if order_info:
            user_id = order_info[1]  # user_id находится во второй колонке
        else:
            # Если заказ не найден в БД, пытаемся извлечь user_id из старого формата
            try:
                user_id = int(order_id_str.split("_")[0])
            except:
                pass
    else:
        # Если order_id строка в старом формате
        try:
            user_id = int(str(order_id).split("_")[0])
        except (ValueError, IndexError):
            user_id = None
            print(f"Не удалось извлечь user_id из order_id: {order_id}")
    
    # Получаем ID пользователя, который нажал кнопку
    admin_chat_id = callback.from_user.id
    
    # Сохраняем данные в состоянии для пользователя, который нажал кнопку
    # Создаем новый FSMContext для этого пользователя
    storage_key = StorageKey(
        chat_id=admin_chat_id,
        user_id=admin_chat_id,
        bot_id=None
    )
    user_state = FSMContext(storage=dp.storage, key=storage_key)
    
    await user_state.update_data(
        cancel_order_id=order_id,
        cancel_user_id=user_id,
        cancel_message_id=callback.message.message_id
    )
    
    # Отправляем тому, кто нажал кнопку, запрос на причину отмены в ЛС
    try:
        order_id_display = f"#{order_id}" if isinstance(order_id, int) else order_id
        await bot.send_message(
            user_id=admin_chat_id,
            text=(
                f"❌ <b>Отмена заказа</b>\n\n"
                f"🆔 ID заказа: <code>{order_id_display}</code>\n"
                f"👤 Пользователь: <code>{user_id if user_id else 'неизвестен'}</code>\n\n"
                f"Пожалуйста, укажите причину отмены заказа:"
            ),
            parse_mode='HTML'
        )
        
        # Устанавливаем состояние для ввода причины для пользователя, который нажал кнопку
        await user_state.set_state(ProfileStatesGroup.cancel_order_reason)
        print(f"✅ Состояние cancel_order_reason установлено для пользователя {admin_chat_id}")
        await callback.answer("Запрос на причину отмены отправлен вам в ЛС", show_alert=True)
        
        # Убираем кнопки у сообщения с заказом
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except:
            pass
            
    except Exception as e:
        error_msg = str(e).lower()
        print(f"Ошибка при отправке запроса: {e}")
        await callback.message.answer(
            "Не удалось отправить запрос в личные сообщения. "
            "Пожалуйста, укажите причину отмены здесь.",
            parse_mode='HTML'
        )
        storage_key = StorageKey(
            chat_id=callback.from_user.id,
            user_id=callback.from_user.id,
            bot_id=None
        )
        user_state = FSMContext(storage=dp.storage, key=storage_key)
        await user_state.update_data(
            cancel_order_id=order_id,
            cancel_user_id=user_id,
            cancel_message_id=callback.message.message_id
        )
        await user_state.set_state(ProfileStatesGroup.cancel_order_reason)
        await callback.answer("Укажите причину отмены", show_alert=True)


# Обработчик ввода причины отмены заказа (вводит тот, кто нажал кнопку)
@form_router.message(ProfileStatesGroup.cancel_order_reason)
async def cancel_order_reason_handler(message: types.Message, state: FSMContext):
    """Обработчик ввода причины отмены заказа - вводит тот, кто нажал кнопку, бот отправляет пользователю"""
    
    print(f"🔍 Получено сообщение в состоянии cancel_order_reason от пользователя {message.from_user.id}: {message.text}")
    
    data = await state.get_data()
    order_id = data.get('cancel_order_id')
    user_id = data.get('cancel_user_id')
    reason = message.text
    
    print(f"🔍 Данные из состояния: order_id={order_id}, user_id={user_id}")
    
    if not order_id:
        await message.answer("Ошибка: не найден ID заказа")
        await state.clear()
        return
    
    # Если user_id не был сохранен, пытаемся извлечь из order_id
    if not user_id:
        try:
            user_id = int(order_id.split("_")[0])
        except (ValueError, IndexError):
            user_id = None
            print(f"Не удалось извлечь user_id из order_id: {order_id}")
    
    # Отправляем сообщение пользователю о отмене заказа с причиной
    if user_id:
        try:
            order_id_display = f"#{order_id}" if isinstance(order_id, int) else order_id
            await bot.send_message(
                user_id=user_id,
                text=(
                    f"❌ <b>Ваш заказ отменен</b>\n\n"
                    f"🆔 ID заказа: <code>{order_id_display}</code>\n"
                    f"📝 Причина отмены: {reason}\n\n"
                    f"Если у вас возникли вопросы, свяжитесь с нами."
                ),
                parse_mode='HTML'
            )
            print(f"✅ Сообщение об отмене заказа отправлено пользователю {user_id}")
        except Exception as user_error:
            print(f"❌ Не удалось отправить сообщение пользователю {user_id}: {user_error}")
            await message.answer(
                f"❌ Ошибка: не удалось отправить сообщение пользователю.\n"
                f"Ошибка: {str(user_error)}"
            )
    else:
        await message.answer("Ошибка: не найден ID пользователя")
    
    # Групповая рассылка отмен отключена - заказы идут только админам
    
    # Возвращаем админа в главное меню после обработки причины отмены
    kb = [[types.KeyboardButton(text="📃 Выбрать товар"), types.KeyboardButton(text="📲 Консультация")]]
    keyboard = inline_menu(kb)
    await message.answer(
        f"Здравствуй, {hbold(message.from_user.full_name)}!\n\n<i>Выберите действие</i>",
        parse_mode='html',
        reply_markup=keyboard
    )
    await state.set_state(ProfileStatesGroup.menu_start)
    print(f"✅ Пользователь {message.from_user.id} возвращен в главное меню")


# Ловим ответ после выбора товара в котегории
@form_router.message(ProfileStatesGroup.insaid_tovar)
async def load_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    data = await state.get_data()

    if message.text == "📦 Корзина":
        await show_basket(message, state)
        return

    # Обработка текстовых сообщений (для обратной совместимости)
    if message.text == "Назад ⬅" or message.text == "⬅ Назад":
        await categories(message, answer_text="<b>Выберите категорию</b>")
        await state.set_state(ProfileStatesGroup.categories)
        return

    if message.text == "Вернуть в меню категорий ⬅":
        await categories(message, answer_text="<b>Выберите категорию</b>")
        await state.set_state(ProfileStatesGroup.categories)
        return
    
    # Обработка нажатий на товары из меню
    else:
        global name
        display_name = message.text
        name = display_name
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()
        cursor.execute("SELECT * FROM list_gribs WHERE name=? ORDER BY id", (display_name,))
        records = cursor.fetchall()
        
        if len(records) == 0:
            return  # Товар не найден
        if len(records) > 0:
            await show_product_card(message, state, records[0], display_name=display_name)
            sqlite_connection.close()
            await state.set_state(ProfileStatesGroup.insaid_tovar)

# Оплата товаров ДЛЯ ПОЧТА РФ ЕСЛИ 1 АДРЕС ИЛИ БОЛЕЕ 1
@form_router.message(ProfileStatesGroup.pay_cart)
async def load_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    data = await state.get_data()

    check = ['Оплатил ОЗОН карту', 'Оплатил СБП']
    user_address = await get_address_for_user(message.from_user.id, 'Яндекс доставка')
    if data['address'] != '' and message.text in check:
        str_address = data['address']
        user_products = await get_basket_for_user(message.from_user.id)
        korzina = []
        pay = DELIVERY_YANDEX_PRICE
        for i, (product_id, product, count) in enumerate(user_products, 1):
            products_str = f"{i}) {product} {count} шт\n"
            product_info = await get_basket_info_product_by_id(product_id)
            if not product_info or len(product_info) == 0:
                korzina.append(f"{products_str}Товар: {product}, Количество: {count} шт")
                continue
            price = int(str(product_info[0][3]).replace("₽", "")) * count
            korzina.append(f"{products_str}Цена: {price}💵Вес: {product_info[0][2]}⚖")
            pay += price
        korzina_str = "\n".join(korzina)

        # Получаем имя пользователя
        from_user = ''
        if message.from_user.username is not None and len(message.from_user.username) > 1:
            from_user = message.from_user.username
        else:
            from_user = 'Нет @имени_пользователя'

        if len(from_user) < 1:
            from_user = 'У пользователя нет логина'
        
        # Отправляем заказ администраторам
        await send_order_to_admins(
            user_id=message.from_user.id,
            username=from_user,
            payment_method=message.text,
            delivery_type='Яндекс доставка',
            address=str_address,
            total_price=pay
        )

        await message.answer(
            text="Ваш заказ принят, ожидайте ответа оператора.\nОбычно это занимает около 1-3 часов\n\nМожете продолжить покупки и просмотр наших товаров 👍")
        kb = [
            [types.KeyboardButton(text="Вернутся на главную ⬅"), types.KeyboardButton(text="📦 Корзина")],
            [types.KeyboardButton(text="🌿 Рапэ племенное"),
             types.KeyboardButton(text="🍄 Мухоморы  шляпки")],
            [types.KeyboardButton(text="🦔 Цельный гриб"),
             types.KeyboardButton(text="💊 Микродозинг в капсулах")],
            [types.KeyboardButton(text="⭐ Молотый"), types.KeyboardButton(text="💧 Капли для глаз")],
            [types.KeyboardButton(text="🍄 Мухоморные крема"), types.KeyboardButton(text="🌱 Чай")],
            [types.KeyboardButton(text="🥥 Мази"), types.KeyboardButton(text="📑 Разное")],
            [types.KeyboardButton(text="⚜ Благовония")]
        ]

        keyboard = inline_menu(kb)
        await bot.send_message(message.chat.id, text="<b>Выберите категорию</b>", reply_markup=keyboard, parse_mode='html')
        await state.set_state(ProfileStatesGroup.categories)
        await state.update_data(address='')
        await clear_basket(message.from_user.id)
    else:
        if message.text in check:
            str_address = ''
            for i, (address) in enumerate(user_address, 1):
                str_address += address[0]

            user_products = await get_basket_for_user(message.from_user.id)
            korzina = []
            pay = DELIVERY_YANDEX_PRICE
            for i, (product_id, product, count) in enumerate(user_products, 1):
                products_str = f"{i}) {product} {count} шт\n"
                product_info = await get_basket_info_product_by_id(product_id)
                if not product_info or len(product_info) == 0:
                    korzina.append(f"{products_str}Товар: {product}, Количество: {count} шт")
                    continue
                price = int(str(product_info[0][3]).replace("₽", "")) * count
                korzina.append(f"{products_str}Цена: {price}💵Вес: {product_info[0][2]}⚖")
                pay += price
            korzina_str = "\n".join(korzina)

            # Получаем имя пользователя
            from_user = ''
            if message.from_user.username is not None and len(message.from_user.username) > 1:
                from_user = message.from_user.username
            else:
                from_user = 'Нет @имени_пользователя'

            if len(from_user) < 1:
                from_user = 'У пользователя нет логина'
            
            # Отправляем заказ администраторам
            await send_order_to_admins(
                user_id=message.from_user.id,
                username=from_user,
                payment_method=message.text,
                delivery_type='Яндекс доставка',
                address=str_address,
                total_price=pay
            )

            await message.answer(
                text="Ваш заказ принят, ожидайте ответа оператора.\nОбычно это занимает около 1-3 часов\n\nМожете продолжить покупки и просмотр наших товаров 👍")
            kb = [
                [types.KeyboardButton(text="Вернутся на главную ⬅"), types.KeyboardButton(text="📦 Корзина")],
                [types.KeyboardButton(text="🌿 Рапэ племенное"),
                 types.KeyboardButton(text="🍄 Мухоморы  шляпки")],
                [types.KeyboardButton(text="🦔 Цельный гриб"),
                 types.KeyboardButton(text="💊 Микродозинг в капсулах")],
                [types.KeyboardButton(text="⭐ Молотый"), types.KeyboardButton(text="💧 Капли для глаз")],
                [types.KeyboardButton(text="🍄 Мухоморные крема"), types.KeyboardButton(text="🌱 Чай")],
                [types.KeyboardButton(text="🥥 Мази"), types.KeyboardButton(text="📑 Разное")],
                [types.KeyboardButton(text="⚜ Благовония")]
            ]
            keyboard = inline_menu(kb)
            await bot.send_message(message.chat.id, text="<b>Выберите категорию</b>", reply_markup=keyboard, parse_mode='html')
            await state.set_state(ProfileStatesGroup.categories)
            await clear_basket(message.from_user.id)
        else:
            kb = [
                [types.KeyboardButton(text=f"Главное меню ⬅"), types.KeyboardButton(text=f"☑ Забрать из магазина")],
                [types.KeyboardButton(text=f"Яндекс доставка 🚚")],
                [types.KeyboardButton(text=f"Доставка СДЕК 🚛")],
            ]
            keyboard = inline_menu(kb)
            await message.answer(
                f"Выберите доставку\n\nДалее нужно будет указать ваши данные для доставки товара\n\nСпасибо, что выбираете нас!",
                reply_markup=keyboard)
            await state.set_state(ProfileStatesGroup.addressUSER)


# Оплата товаров ДЛЯ СДЕК ЕСЛИ 1 АДРЕС
@form_router.message(ProfileStatesGroup.pay_cart_CDEK)
async def load_name_CDEK(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    data = await state.get_data()
    user_address = await get_address_for_user(message.from_user.id, 'СДЕК')
    check = ['Оплатил ОЗОН карту', 'Оплатил СБП']
    if data['address_CDEK'] != '' and message.text in check:
        str_address = data['address_CDEK']
        user_products = await get_basket_for_user(message.from_user.id)
        korzina = []
        pay = DELIVERY_CDEK_PRICE
        for i, (product_id, product, count) in enumerate(user_products, 1):
            products_str = f"{i}) {product} {count} шт\n"
            product_info = await get_basket_info_product_by_id(product_id)
            if not product_info or len(product_info) == 0:
                korzina.append(f"{products_str}Товар: {product}, Количество: {count} шт")
                continue
            price = int(str(product_info[0][3]).replace("₽", "")) * count
            korzina.append(f"{products_str}Цена: {price}💵Вес: {product_info[0][2]}⚖")
            pay += price
        korzina_str = "\n".join(korzina)

        # Получаем имя пользователя
        from_user = ''
        if message.from_user.username is not None and len(message.from_user.username) > 1:
            from_user = message.from_user.username
        else:
            from_user = 'Нет @имени_пользователя'

        if len(from_user) < 1:
            from_user = 'У пользователя нет логина'
        
        # Отправляем заказ администраторам
        await send_order_to_admins(
            user_id=message.from_user.id,
            username=from_user,
            payment_method=message.text,
            delivery_type='СДЕК',
            address=str_address,
            total_price=pay
        )

        await message.answer(
            text="Ваш заказ принят, ожидайте ответа оператора.\nОбычно это занимает около 1-3 часов\n\nМожете продолжить покупки и просмотр наших товаров 👍")
        kb = [
            [types.KeyboardButton(text="Вернутся на главную ⬅"), types.KeyboardButton(text="📦 Корзина")],
            [types.KeyboardButton(text="🌿 Рапэ племенное"),
             types.KeyboardButton(text="🍄 Мухоморы  шляпки")],
            [types.KeyboardButton(text="🦔 Цельный гриб"),
             types.KeyboardButton(text="💊 Микродозинг в капсулах")],
            [types.KeyboardButton(text="⭐ Молотый"), types.KeyboardButton(text="💧 Капли для глаз")],
            [types.KeyboardButton(text="🍄 Мухоморные крема"), types.KeyboardButton(text="🌱 Чай")],
            [types.KeyboardButton(text="🥥 Мази"), types.KeyboardButton(text="📑 Разное")],
            [types.KeyboardButton(text="⚜ Благовония")]
        ]

        keyboard = inline_menu(kb)
        await bot.send_message(message.chat.id, text="<b>Выберите категорию</b>", reply_markup=keyboard,
                               parse_mode='html')
        await state.set_state(ProfileStatesGroup.categories)
        data['address_CDEK'] = ''  # ОТЧИЩАЕМ АДРЕС
        await state.update_data(address_CDEK='')
        await clear_basket(message.from_user.id)
    else:
        if message.text in check:
            str_address = ''
            for i, (address) in enumerate(user_address, 1):
                str_address += address[0]

            user_products = await get_basket_for_user(message.from_user.id)
            korzina = []
            pay = DELIVERY_CDEK_PRICE
            for i, (product_id, product, count) in enumerate(user_products, 1):
                products_str = f"{i}) {product} {count} шт\n"
                product_info = await get_basket_info_product_by_id(product_id)
                if not product_info or len(product_info) == 0:
                    korzina.append(f"{products_str}Товар: {product}, Количество: {count} шт")
                    continue
                price = int(str(product_info[0][3]).replace("₽", "")) * count
                korzina.append(f"{products_str}Цена: {price}💵Вес: {product_info[0][2]}⚖")
                pay += price
            korzina_str = "\n".join(korzina)

            # Получаем имя пользователя
            from_user = ''
            if message.from_user.username is not None and len(message.from_user.username) > 1:
                from_user = message.from_user.username
            else:
                from_user = 'Нет @имени_пользователя'

            if len(from_user) < 1:
                from_user = 'У пользователя нет логина'
            
            # Отправляем заказ администраторам
            await send_order_to_admins(
                user_id=message.from_user.id,
                username=from_user,
                payment_method=message.text,
                delivery_type='СДЕК',
                address=str_address,
                total_price=pay
            )

            await message.answer(
                text="Ваш заказ принят, ожидайте ответа оператора.\nОбычно это занимает около 1-3 часов\n\nМожете продолжить покупки и просмотр наших товаров 👍")
            kb = [
                [types.KeyboardButton(text="Вернутся на главную ⬅"), types.KeyboardButton(text="📦 Корзина")],
                [types.KeyboardButton(text="🌿 Рапэ племенное"),
                 types.KeyboardButton(text="🍄 Мухоморы  шляпки")],
                [types.KeyboardButton(text="🦔 Цельный гриб"),
                 types.KeyboardButton(text="💊 Микродозинг в капсулах")],
                [types.KeyboardButton(text="⭐ Молотый"), types.KeyboardButton(text="💧 Капли для глаз")],
                [types.KeyboardButton(text="🍄 Мухоморные крема"), types.KeyboardButton(text="🌱 Чай")],
                [types.KeyboardButton(text="🥥 Мази"), types.KeyboardButton(text="📑 Разное")],
                [types.KeyboardButton(text="⚜ Благовония")]
            ]
            keyboard = inline_menu(kb)
            await bot.send_message(message.chat.id, text="<b>Выберите категорию</b>", reply_markup=keyboard, parse_mode='html')
            await state.set_state(ProfileStatesGroup.categories)
        else:
            kb = [
                [types.KeyboardButton(text=f"Главное меню ⬅"), types.KeyboardButton(text=f"☑ Забрать из магазина")],
                [types.KeyboardButton(text=f"Яндекс доставка 🚚")],
                [types.KeyboardButton(text=f"Доставка СДЕК 🚛")],
            ]
            keyboard = inline_menu(kb)
            await message.answer(
                f"Выберите доставку\n\nДалее нужно будет указать ваши данные для доставки товара\n\nСпасибо, что выбираете нас!",
                reply_markup=keyboard)
            await state.set_state(ProfileStatesGroup.addressUSER)


# Обработчик delete_product_one оставлен для обратной совместимости, но больше не используется
# Удаление товаров теперь происходит через inline кнопки



@form_router.message(ProfileStatesGroup.count_insaid_tovar)
async def load_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)  # Устанавливаем данные
    data = await state.get_data()  # Получаем данные из состояния

    if str(message.text) == "Главное меню ⬅":
        await categories(message, answer_text="<b>Выберите категорию</b>")
        await state.set_state(ProfileStatesGroup.categories)
    else:
        try:
            count = int(message.text)
            product_id = data.get('product_id')
            product_name = data.get('product_name', '')
            
            if not product_id:
                # Если product_id нет, получаем его по имени
                product_info = await get_basket_info_product(product_name)
                if product_info:
                    product_id = product_info[0][0]
                else:
                    await message.answer("Ошибка: товар не найден")
                    return
            
            await add_to_basket(user_id=message.from_user.id, product_id=product_id, product=product_name, counnt=count)
            
            # Автоматически перекидываем в меню категорий
            await message.answer(f"Товар успешно добавлен в количестве: {count}шт")
            await categories(message, answer_text="<b>Выберите категорию</b>")
            await state.set_state(ProfileStatesGroup.categories)
        except ValueError:
            await message.answer("Пожалуйста, введите число")


# ОБРАБОТКА КОГДА АДРЕСОВ БОЛЬШЕ 2 У ПОЧТЫ РФ
@form_router.message(ProfileStatesGroup.pay_cart_many_address)
async def load_name_many(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)  # Устанавливаем данные
    data = await state.get_data()  # Получаем данные из состояния
    search_address = await search_address_in_user(message.text, 'Яндекс доставка')

    if len(search_address) > 0:
        await state.update_data(address=message.text)
        user_products = await get_basket_for_user(message.from_user.id)
        pay = 0
        for i, (product_id, product, count) in enumerate(user_products, 1):
            product_info = await get_basket_info_product_by_id(product_id)
            if not product_info or len(product_info) == 0:
                continue  # Пропускаем товары, которые не найдены
            price = int(str(product_info[0][3]).replace("₽", "")) * count
            pay += price

        pay += DELIVERY_YANDEX_PRICE
        kb = [
            [types.KeyboardButton(text=f"Оплатил СБП")],
            [types.KeyboardButton(text=f"Оплатил ОЗОН карту")],
            [types.KeyboardButton(text=f"Отмена")],
        ]
        keyboard = inline_menu(kb)
        output_code = await photo()

        await message.answer_photo(
            BufferedInputFile(
                output_code.read(),
                filename="code_photo.png",
            ),
            caption="На картинке выше расположен QR-код СБП." + "\n\n" + "К оплате " + str(
                pay) + "₽ " + "\n" + "Вид доставки: Яндекс доставка" + "\n\n" + "Виды оплаты:" + "\n" + "Карта ОЗОН " + "`" + OZON_CARD_NUMBER + "`" + "\n\n" + "После оплаты, нажмите ОПЛАТИЛ и ожидайте уведомления",
            parse_mode='Markdown', reply_markup=keyboard)
        await state.set_state(ProfileStatesGroup.pay_cart)


# ОБРАБОТКА КОГДА АДРЕСОВ БОЛЬШЕ 2 У СДЕК
@form_router.message(ProfileStatesGroup.pay_cart_many_address_CDEK)
async def load_name_many_CDEK(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)  # Устанавливаем данные

    search_address = await search_address_in_user(message.text, 'СДЕК')
    if len(search_address) > 0:
        await state.update_data(address_CDEK=message.text)
        user_products = await get_basket_for_user(message.from_user.id)
        pay = 0
        for i, (product_id, product, count) in enumerate(user_products, 1):
            product_info = await get_basket_info_product_by_id(product_id)
            if not product_info or len(product_info) == 0:
                continue  # Пропускаем товары, которые не найдены
            price = int(str(product_info[0][3]).replace("₽", "")) * count
            pay += price

        pay += DELIVERY_CDEK_PRICE
        kb = [
            [types.KeyboardButton(text=f"Оплатил СБП")],
            [types.KeyboardButton(text=f"Оплатил ОЗОН карту")],
            [types.KeyboardButton(text=f"Отмена")],
        ]
        keyboard = inline_menu(kb)
        output_code = await photo()
        await message.answer_photo(
            BufferedInputFile(
                output_code.read(),
                filename="code_photo.png",
            ),
            caption="На картинке выше расположен QR-код СБП." + "\n\n" + "К оплате " + str(
                pay) + "₽ " + "\n" + "Вид доставки: Яндекс доставка" + "\n\n" + "Виды оплаты:" + "\n" + "Карта ОЗОН " + "`" + OZON_CARD_NUMBER + "`" + "\n\n" + "После оплаты, нажмите ОПЛАТИЛ и ожидайте уведомления",
            parse_mode='Markdown', reply_markup=keyboard)

        await state.set_state(ProfileStatesGroup.pay_cart_CDEK)
    else:
        kb = [
            [types.KeyboardButton(text=f"Главное меню ⬅")],
            [types.KeyboardButton(text=f"Яндекс доставка 🚚")],
            [types.KeyboardButton(text=f"Доставка СДЕК 🚛")],
        ]
        keyboard = inline_menu(kb)
        await message.answer(
            f"Выберите доставку\n\nДалее нужно будет указать ваши данные для доставки товара\n\nСпасибо, что выбираете нас!",
            reply_markup=keyboard)
        await state.set_state(ProfileStatesGroup.addressUSER)


# ВЫБОР ОПЛАТИТЬ ИЛИ ПРОДОЛЖИТЬ ПОКУПКИ
@form_router.message(ProfileStatesGroup.vibor_pay_or_back)
async def load_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)  # Устанавливаем данные
    data = await state.get_data()

    if message.text == "Оплатить (Яндекс доставка)":  # ЕМУ должен выводится список его адресов
        type_a = "Яндекс доставка"
        user_address = await get_address_for_user(message.from_user.id, type_a)

        if len(user_address) > 1:  # ЕСЛИ АДРЕСОВ НА ПОЧТА РФ >>>>> 2
            kb = [
                [types.KeyboardButton(text=f"Вернутся на главную ⬅")]
            ]
            for i, (address, type_a) in enumerate(user_address, 1):

                kb.append([types.KeyboardButton(
                    text=f"{address}")])

                keyboard = inline_menu(kb)
            await message.answer("Выберите данные, по которым хотите получить и оплатить далее товар",
                                 reply_markup=keyboard)
            await state.set_state(ProfileStatesGroup.pay_cart_many_address)
        else:
            str_address = ''
            for i, (address) in enumerate(user_address, 1):
                str_address += address[0]
                user_products = await get_basket_for_user(message.from_user.id)
                pay = 0
                if len(user_products) > 0:
                    for i, (product_id, product, count) in enumerate(user_products, 1):
                        product_info = await get_basket_info_product_by_id(product_id)
                        if not product_info or len(product_info) == 0:
                            continue  # Пропускаем товары, которые не найдены
                        price = int(str(product_info[0][3]).replace("₽", "")) * count
                        pay += price

                    pay += DELIVERY_YANDEX_PRICE
                    kb = [
                        [types.KeyboardButton(text=f"Оплатил СБП")],
                        [types.KeyboardButton(text=f"Оплатил ОЗОН карту")],
                        [types.KeyboardButton(text=f"Отмена")],
                    ]
                    keyboard = inline_menu(kb)
                    output_code = await photo()
                    await message.answer_photo(
                        BufferedInputFile(
                            output_code.read(),
                            filename="code_photo.png",
                        ),
                        caption="На картинке выше расположен QR-код СБП." + "\n\n" + "К оплате " + str(
                            pay) + "₽ " + "\n" + "Вид доставки: Яндекс доставка" + "\n\n" + "Виды оплаты:" + "\n" + "Карта ОЗОН " + "`" + OZON_CARD_NUMBER + "`" + "\n\n" + "После оплаты, нажмите ОПЛАТИЛ и ожидайте уведомления",
                        parse_mode='Markdown', reply_markup=keyboard)

                    await state.set_state(ProfileStatesGroup.pay_cart)
                else:
                    await categories(message, answer_text="Вы вернулись в главное меню")
                    await state.set_state(ProfileStatesGroup.categories)


    elif message.text == "Оплатить (СДЕК)":
        type_a = "СДЕК"
        user_address = await get_address_for_user(message.from_user.id, type_a)

        if len(user_address) > 1:  # ЕСЛИ АДРЕСОВ НА СДЕК >>>>> 2
            kb = [
                [types.KeyboardButton(text=f"Вернутся на главную ⬅")]
            ]
            for i, (address, type_a) in enumerate(user_address, 1):

                kb.append([types.KeyboardButton(
                    text=f"{address}")])

                keyboard = inline_menu(kb)
            await message.answer("Выберите данные, по которым хотите получить товар", reply_markup=keyboard)
            await state.set_state(ProfileStatesGroup.pay_cart_many_address_CDEK)
        else:
            str_address = ''
            for i, (address) in enumerate(user_address, 1):
                str_address += address[0]
                user_products = await get_basket_for_user(message.from_user.id)
                pay = 0
                if len(user_products) > 0:
                    for i, (product_id, product, count) in enumerate(user_products, 1):
                        product_info = await get_basket_info_product_by_id(product_id)
                        if not product_info or len(product_info) == 0:
                            continue  # Пропускаем товары, которые не найдены
                        price = int(str(product_info[0][3]).replace("₽", "")) * count
                        pay += price

                    pay += DELIVERY_CDEK_PRICE
                    kb = [
                        [types.KeyboardButton(text=f"Оплатил СБП")],
                        [types.KeyboardButton(text=f"Оплатил ОЗОН карту")],
                        [types.KeyboardButton(text=f"Отмена")],
                    ]
                    keyboard = inline_menu(kb)
                    output_code = await photo()
                    await message.answer_photo(
                        BufferedInputFile(
                            output_code.read(),
                            filename="code_photo.png",
                        ),
                        caption="На картинке выше расположен QR-код СБП." + "\n\n" + "К оплате " + str(
                            pay) + "₽ " + "\n" + "Вид доставки: Яндекс доставка" + "\n\n" + "Виды оплаты:" + "\n" + "Карта ОЗОН " + "`" + OZON_CARD_NUMBER + "`" + "\n\n" + "После оплаты, нажмите ОПЛАТИЛ и ожидайте уведомления",
                        parse_mode='Markdown', reply_markup=keyboard)
                    await state.set_state(ProfileStatesGroup.pay_cart_CDEK)
                else:
                    await categories(message, answer_text="Вы вернулись в главное меню")
                    await state.set_state(ProfileStatesGroup.categories)

    elif message.text == 'Продолжить покупки':
        await categories(message, answer_text="Вы вернулись в главное меню")
        await state.set_state(ProfileStatesGroup.categories)

# СОХРАНЯЕМ ДАННЫЕ ДЛЯ ПОЧТЫ РФ В БАЗУ 250 р доставка
@form_router.message(ProfileStatesGroup.address_processing)
async def load_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)  # Устанавливаем данные
    data = await state.get_data()

    type = 'Яндекс доставка'
    if message.text != 'Вернутся на главную ⬅':
        await add_to_address(user_id=message.from_user.id, address=str(message.text), type_a=type)
        kb = [
            [types.KeyboardButton(text="Оплатить (Яндекс доставка)")],
            [types.KeyboardButton(text="Продолжить покупки")],
        ]
        keyboard = inline_menu(kb)
        await message.answer(
            "Ваши данные сохранены. \n\nДалее у вас есть выбор, продолжить просмотр товаров и пополнять корзину\n(система запомнит ваши данные, который указали вы для доставки),\nлибо продолжить оплату",
            reply_markup=keyboard)
        await state.set_state(ProfileStatesGroup.vibor_pay_or_back)
    else:
        await categories(message, answer_text="Вы вернулись в главное меню")
        await state.set_state(ProfileStatesGroup.categories)


@form_router.message(ProfileStatesGroup.pay_cart_BCE)
async def load_name_BCE(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)  # Устанавливаем данные
    data = await state.get_data()

    check = ['Оплатил ОЗОН карту', 'Оплатил СБП']
    if data['address_BCE'] != '' and message.text in check:
        str_address = data['address_BCE']
        user_products = await get_basket_for_user(message.from_user.id)
        korzina = []
        pay = DELIVERY_CDEK_PRICE
        for i, (product_id, product, count) in enumerate(user_products, 1):
            products_str = f"{i}) {product} {count} шт\n"
            product_info = await get_basket_info_product_by_id(product_id)
            if not product_info or len(product_info) == 0:
                korzina.append(f"{products_str}Товар: {product}, Количество: {count} шт")
                continue
            price = int(str(product_info[0][3]).replace("₽", "")) * count
            korzina.append(f"{products_str}Цена: {price}💵Вес: {product_info[0][2]}⚖")
            pay += price
        korzina_str = "\n".join(korzina)

        # Получаем имя пользователя
        from_user = ''
        if message.from_user.username is not None and len(message.from_user.username) > 1:
            from_user = message.from_user.username
        else:
            from_user = 'Нет @имени_пользователя'

        if len(from_user) < 1:
            from_user = 'У пользователя нет логина'
        
        # Определяем тип доставки
        delivery_type = 'СДЕК' if 'СДЕК' in str_address or 'CDEK' in str_address else 'Яндекс доставка'
        
        # Отправляем заказ администраторам
        await send_order_to_admins(
            user_id=message.from_user.id,
            username=from_user,
            payment_method=message.text,
            delivery_type=delivery_type,
            address=str_address,
            total_price=pay
        )

        await message.answer(
            text="Ваш заказ принят, ожидайте ответа оператора.\nОбычно это занимает около 1-3 часов\n\nМожете продолжить покупки и просмотр наших товаров 👍")
        kb = [
            [types.KeyboardButton(text="Вернутся на главную ⬅"), types.KeyboardButton(text="📦 Корзина")],
            [types.KeyboardButton(text="🌿 Рапэ племенное"),
             types.KeyboardButton(text="🍄 Мухоморы  шляпки")],
            [types.KeyboardButton(text="🦔 Цельный гриб"),
             types.KeyboardButton(text="💊 Микродозинг в капсулах")],
            [types.KeyboardButton(text="⭐ Молотый"), types.KeyboardButton(text="💧 Капли для глаз")],
            [types.KeyboardButton(text="🍄 Мухоморные крема"), types.KeyboardButton(text="🌱 Чай")],
            [types.KeyboardButton(text="🥥 Мази"), types.KeyboardButton(text="📑 Разное")],
            [types.KeyboardButton(text="⚜ Благовония")]
        ]

        keyboard = inline_menu(kb)
        await bot.send_message(message.chat.id, text="<b>Выберите категорию</b>", reply_markup=keyboard,
                               parse_mode='html')
        await state.set_state(ProfileStatesGroup.categories)
        await state.update_data(address_BCE='')
        await clear_basket(message.from_user.id)
    else:
        kb = [
            [types.KeyboardButton(text=f"Главное меню ⬅")],
            [types.KeyboardButton(text=f"Яндекс доставка 🚚")],
            [types.KeyboardButton(text=f"Доставка СДЕК 🚛")],
        ]
        keyboard = inline_menu(kb)
        await message.answer(
            f"Отмена!\nВыберите доставку\n\nДалее нужно будет указать ваши данные для доставки товара\n\nСпасибо, что выбираете нас!",
            reply_markup=keyboard)
        await state.set_state(ProfileStatesGroup.addressUSER)


# ОБРАБОТКА ДЛЯ ОБОИХ ВИДОВ ДОСТАВКИ
@form_router.message(ProfileStatesGroup.address_processing_BCE)
async def load_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)  # Устанавливаем данные

    user_address = await search_BCE(message.text)
    if len(user_address) > 0 and message.text != 'Вернутся назад ⬅':

        for i in user_address:
            type_address = i
        pay = 0
        user_products = await get_basket_for_user(message.from_user.id)
        for i, (product_id, product, count) in enumerate(user_products, 1):
            product_info = await get_basket_info_product_by_id(product_id)
            if not product_info or len(product_info) == 0:
                continue  # Пропускаем товары, которые не найдены
            price = int(str(product_info[0][3]).replace("₽", "")) * count
            pay += price

        if type_address == 'Яндекс доставка':
            pay += DELIVERY_YANDEX_PRICE
        else:
            pay += DELIVERY_CDEK_PRICE

        # data['address_BCE'] = str(type_address[1]) + ":  " + message.text
        await state.update_data(address_BCE=str(type_address[1]) + ":  " + message.text)
        kb = [
            [types.KeyboardButton(text=f"Оплатил СБП")],
            [types.KeyboardButton(text=f"Оплатил ОЗОН карту")],
            [types.KeyboardButton(text=f"Отмена")],
        ]
        keyboard = inline_menu(kb)
        output_code = await photo()
        await message.answer_photo(
            BufferedInputFile(
                output_code.read(),
                filename="code_photo.png",
            ),
            caption="На картинке выше расположен QR-код СБП." + "\n\n" + "К оплате " + str(
                pay) + "₽ " + "\n" + "Вид доставки: Яндекс доставка" + "\n\n" + "Виды оплаты:" + "\n" + "Карта ОЗОН " + "`" + OZON_CARD_NUMBER + "`" + "\n\n" + "После оплаты, нажмите ОПЛАТИЛ и ожидайте уведомления",
            parse_mode='Markdown', reply_markup=keyboard)

        await state.set_state(ProfileStatesGroup.pay_cart_BCE)
    else:
        kb = [
            [types.KeyboardButton(text=f"Главное меню ⬅")],
            [types.KeyboardButton(text=f"Яндекс доставка 🚚")],
            [types.KeyboardButton(text=f"Доставка СДЕК 🚛")],
        ]
        keyboard = inline_menu(kb)
        if message.text == 'Вернутся назад ⬅':
            await message.answer(
                f"Выберите доставку\n\nДалее нужно будет указать ваши данные для доставки товара\n\nСпасибо, что выбираете нас!",
                reply_markup=keyboard)
        else:
            await message.answer(
                f"Ваш запрос не выдал результата\n\nВыберите доставку\n\nДалее нужно будет указать ваши данные для доставки товара\n\nСпасибо, что выбираете нас!",
                reply_markup=keyboard)
        await state.set_state(ProfileStatesGroup.addressUSER)


# СОХРАНЯЕМ ДАННЫЕ ДЛЯ СДЕК В БАЗУ 300 р доставка
@form_router.message(ProfileStatesGroup.address_processing_CDEK)
async def load_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)

    type = 'СДЕК'
    if message.text != 'Вернутся на главную ⬅':
        await add_to_address(user_id=message.from_user.id, address=str(message.text), type_a=type)
        kb = [
            [types.KeyboardButton(text="Оплатить (СДЕК)")],
            [types.KeyboardButton(text="Продолжить покупки")],
        ]
        keyboard = inline_menu(kb)
        await message.answer(
            "Ваши данные сохранены. \n\nДалее у вас есть выбор, продолжить просмотр товаров и пополнять корзину\n(система запомнит ваши данные, который указали вы для доставки),\nлибо продолжить оплату",
            reply_markup=keyboard)
        await state.set_state(ProfileStatesGroup.vibor_pay_or_back)
    else:
        await categories(message, answer_text="Вы вернулись в главное меню")
        await state.set_state(ProfileStatesGroup.categories)


# БЛОК ВЫБОРА ДОСТАВКИ
@form_router.message(ProfileStatesGroup.addressUSER)
async def load_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)

    if message.text == 'Яндекс доставка 🚚':
        kb = [
            [types.KeyboardButton(text="Вернутся на главную ⬅")]
        ]
        keyboard = inline_menu(kb)
        await message.answer(
            "Введите персональные данные для доставки\nФИО\nЛичный адрес(чтобы мы доставили в ближайший пункт выдачи)\nИНДЕКС\nНомер телефона\n\n✅ Данные конфиденциальны ✅\nСтоимость доставки 250₽ \n\nПример: Иванов Иван Иванович\nАдрес: Пушкина 17/5\n4000504\n+79870542200\n\nНЕ ОБЯЗАТЕЛЬНО ЧЕРЕЗ СТРОЧУ",
            reply_markup=keyboard)
        await state.set_state(ProfileStatesGroup.address_processing)

    elif message.text == '☑ Забрать из магазина':
        text = f"<b>Адрес: {SHOP_ADDRESS}\nВремя работы с {SHOP_HOURS}</b>\n\n<b>Номер телефона: </b><code>{SHOP_PHONE}</code>"
        kb = [
            [types.KeyboardButton(text="Я оплатил наличными")],
            [types.KeyboardButton(text=f"Оплатил СБП")],
            [types.KeyboardButton(text=f"Оплатил ОЗОН карту")],
            [types.KeyboardButton(text=f"Отмена")]
        ]

        keyboard = inline_menu(kb)
        await message.answer(text, parse_mode='html', reply_markup=keyboard)
        output_code = await photo()
        await message.answer_photo(
            BufferedInputFile(
                output_code.read(),
                filename="code_photo.png",
            ),
            caption="На картинке выше расположен QR-код СБП." + "Виды оплаты:" + "\n" + "Карта ОЗОН " + "`" + OZON_CARD_NUMBER + "`" + "\n\n" + "После оплаты, нажмите ОПЛАТИЛ и ожидайте уведомления",
            parse_mode='Markdown')

        await state.set_state(ProfileStatesGroup.zabrat_iz_magaziana)


    elif message.text == 'Доставка СДЕК 🚛':
        kb = [
            [types.KeyboardButton(text="Вернутся на главную ⬅")]
        ]
        keyboard = inline_menu(kb)
        await message.answer(
            "Введите персональные данные для доставки\nФИО\nАдрес ближайшего СДЕК\nНомер телефона\n\n✅ Данные конфиденциальны ✅\nСтоимость доставки 300₽\n\nПример: Иванов Иван Иванович\nАдрес СДЭК: Пушкина 17/5\n+79870542200\n\nНЕ ОБЯЗАТЕЛЬНО ЧЕРЕЗ СТРОЧУ",
            reply_markup=keyboard)
        await state.set_state(ProfileStatesGroup.address_processing_CDEK)

    elif message.text == 'Я вводил данные':
        address_BCE = await search_address_in_user_BCE(user_id=message.from_user.id)
        if len(address_BCE) > 0:
            kb = [
                [types.KeyboardButton(text=f"Вернутся назад ⬅")]
            ]
            for i, (address) in enumerate(address_BCE, 1):
                kb.append([types.KeyboardButton(
                    text=f"{address[0]}")])

                keyboard = inline_menu(kb)
            await message.answer("Выберите данные, по которым хотите получить товар", reply_markup=keyboard)
            await state.set_state(ProfileStatesGroup.address_processing_BCE)
        else:
            kb = [
                [types.KeyboardButton(text=f"Главное меню ⬅"), types.KeyboardButton(text=f"☑ Забрать из магазина")],
                [types.KeyboardButton(text=f"Яндекс доставка 🚚")],
                [types.KeyboardButton(text=f"Доставка СДЕК 🚛")],
            ]
            keyboard = inline_menu(kb)
            await message.answer(
                f"Выберите доставку\n\nДалее нужно будет указать ваши данные для доставки товара\n\nСпасибо, что выбираете нас!",
                reply_markup=keyboard)
            await state.set_state(ProfileStatesGroup.addressUSER)
    else:
        await categories(message, answer_text="Вы вернулись в главное меню")
        await state.set_state(ProfileStatesGroup.categories)



@form_router.message(ProfileStatesGroup.zabrat_iz_magaziana)
async def zabrat_iz_magaziana(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    check = ['Я оплатил наличными', 'Оплатил ОЗОН карту', 'Оплатил СБП']

    if message.text in check:
        """СДЕЛАТЬ ОТЧИСТКУ КОРЗИНЫ"""
        user_products = await get_basket_for_user(message.from_user.id)
        korzina = []
        pay = 0
        for i, (product_id, product, count) in enumerate(user_products, 1):
            products_str = f"{i}) {product} {count} шт\n"
            product_info = await get_basket_info_product_by_id(product_id)
            if not product_info or len(product_info) == 0:
                korzina.append(f"{products_str}Товар: {product}, Количество: {count} шт")
                continue
            price = int(str(product_info[0][3]).replace("₽", "")) * count
            korzina.append(f"{products_str}Цена: {price}💵Вес: {product_info[0][2]}⚖")
            pay += price
        korzina_str = "\n".join(korzina)

        # Получаем имя пользователя
        from_user = ''
        if message.from_user.username is not None and len(message.from_user.username) > 1:
            from_user = message.from_user.username
        else:
            from_user = 'Нет @имени_пользователя'

        if len(from_user) < 1:
            from_user = 'У пользователя нет логина'
        
        # Отправляем заказ администраторам
        await send_order_to_admins(
            user_id=message.from_user.id,
            username=from_user,
            payment_method=message.text,
            delivery_type='Самовывоз',
            address='Заберет из магазина',
            total_price=pay
        )

        await message.answer(
            text="Ваш заказ принят, ожидайте ответа оператора.\nОбычно это занимает около 1-3 часов\n\nМожете продолжить покупки и просмотр наших товаров 👍")
        kb = [
            [types.KeyboardButton(text="Вернутся на главную ⬅"), types.KeyboardButton(text="📦 Корзина")],
            [types.KeyboardButton(text="🌿 Рапэ племенное"),
             types.KeyboardButton(text="🍄 Мухоморы  шляпки")],
            [types.KeyboardButton(text="🦔 Цельный гриб"),
             types.KeyboardButton(text="💊 Микродозинг в капсулах")],
            [types.KeyboardButton(text="⭐ Молотый"), types.KeyboardButton(text="💧 Капли для глаз")],
            [types.KeyboardButton(text="🍄 Мухоморные крема"), types.KeyboardButton(text="🌱 Чай")],
            [types.KeyboardButton(text="🥥 Мази"), types.KeyboardButton(text="📑 Разное")],
            [types.KeyboardButton(text="⚜ Благовония")]
        ]

        keyboard = inline_menu(kb)
        await bot.send_message(message.chat.id, text="<b>Выберите категорию</b>", reply_markup=keyboard, parse_mode='html')
        await state.set_state(ProfileStatesGroup.categories)
        await state.update_data(address='')
        await clear_basket(message.from_user.id)
    else:
        kb = [
            [types.KeyboardButton(text="Вернутся на главную ⬅"), types.KeyboardButton(text="📦 Корзина")],
            [types.KeyboardButton(text="🌿 Рапэ племенное"),
             types.KeyboardButton(text="🍄 Мухоморы  шляпки")],
            [types.KeyboardButton(text="🦔 Цельный гриб"),
             types.KeyboardButton(text="💊 Микродозинг в капсулах")],
            [types.KeyboardButton(text="⭐ Молотый"), types.KeyboardButton(text="💧 Капли для глаз")],
            [types.KeyboardButton(text="🍄 Мухоморные крема"), types.KeyboardButton(text="🌱 Чай")],
            [types.KeyboardButton(text="🥥 Мази"), types.KeyboardButton(text="📑 Разное")],
            [types.KeyboardButton(text="⚜ Благовония")]
        ]

        keyboard = inline_menu(kb)
        await bot.send_message(message.chat.id, text="<b>Выберите категорию</b>", reply_markup=keyboard, parse_mode='html')
        await state.set_state(ProfileStatesGroup.categories)


# КОРЗИНА
@form_router.message(ProfileStatesGroup.basket_menu)
async def load_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)  # Устанавливаем данные
    data = await state.get_data()

    if message.text == "🗑 Очистить корзину":
        await delete_basket_for_user(user_id=int(message.from_user.id))
        await categories(message, answer_text="Ваша корзина успешно очищена")
        await state.set_state(ProfileStatesGroup.categories)

    elif message.text == "☑ Оплатить корзину":
        user_products = await get_basket_for_user(message.from_user.id)
        if len(user_products) > 0:
            kb = [
                [types.KeyboardButton(text=f"Главное меню ⬅"), types.KeyboardButton(text=f"☑ Забрать из магазина")],
                [types.KeyboardButton(text=f"Яндекс доставка 🚚")],
                [types.KeyboardButton(text=f"Доставка СДЕК 🚛")],
            ]
            keyboard = inline_menu(kb)
            await message.answer(
                f"Выберите доставку\n\nДалее нужно будет указать ваши данные для доставки товара\n\nСпасибо, что выбираете нас!",
                reply_markup=keyboard)
            await state.set_state(ProfileStatesGroup.addressUSER)
        else:
            await categories(message, answer_text="<b>Ваша корзина пуста. \nВыберите категорию</b>")
            await state.set_state(ProfileStatesGroup.categories)

    elif message.text == "Вернуться в меню категорий ⬅":
        await categories(message, answer_text="<b>Выберите категорию</b>")
        await state.set_state(ProfileStatesGroup.categories)


@form_router.message(F.text)
async def home(message: types.Message, state: FSMContext):
    if message.text == "Вернуть в меню категорий ⬅":
        await categories(message, answer_text="<b>Выберите категорию</b>")
        await state.set_state(ProfileStatesGroup.categories)
        return
    
    # Обработка "📦 Корзина" удалена отсюда, так как она уже обрабатывается 
    # в специфичных обработчиках состояний (categories, tovar, insaid_tovar)
    
    # Если сообщение не было обработано другими обработчиками - показываем ошибку
    await handle_unknown_message(message, state)


# Обработчик неизвестных сообщений и ошибок
async def handle_unknown_message(message: types.Message, state: FSMContext = None):
    """Обрабатывает неизвестные сообщения и ошибки"""
    # Создаем inline кнопку для перезапуска бота
    inline_kb = [
        [
            types.InlineKeyboardButton(
                text="🔄 Перезапустить бота",
                callback_data="restart_bot"
            )
        ]
    ]
    inline_keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_kb)
    
    await message.answer(
        "❌ <b>Не понял вас</b>\n\n"
        "Пожалуйста, перезапустите бота, чтобы вернуться в главное меню.",
        parse_mode='HTML',
        reply_markup=inline_keyboard
    )


# Обработчик callback для перезапуска бота
@form_router.callback_query(F.data == "restart_bot")
async def restart_bot_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик перезапуска бота - сбрасывает состояние и показывает главное меню"""
    # Очищаем состояние
    await state.clear()
    
    # Показываем главное меню
    kb = [[types.KeyboardButton(text="📃 Выбрать товар"), types.KeyboardButton(text="📲 Консультация")]]
    keyboard = inline_menu(kb)
    
    await callback.message.edit_text(
        f"✅ <b>Бот перезапущен!</b>\n\n"
        f"Здравствуй, {hbold(callback.from_user.full_name)}!\n\n"
        f"<i>Выберите действие</i>",
        parse_mode='HTML'
    )
    
    await callback.message.answer(
        f"Здравствуй, {hbold(callback.from_user.full_name)}!\n\n<i>Выберите действие</i>",
        parse_mode='html',
        reply_markup=keyboard
    )
    
    await state.set_state(ProfileStatesGroup.menu_start)
    await callback.answer("Бот перезапущен!", show_alert=False)
    print(f"✅ Бот перезапущен для пользователя {callback.from_user.id}")


async def main():
    await ensure_database()
    # Проверяем доступность чатов при старте
    from create_bot import admin_id
    
    print("\n" + "="*50)
    print("Проверка настроек бота...")
    print("="*50)
    
    # Проверяем ADMIN_ID
    try:
        keys_list = list(admin_id.keys())
        if keys_list:
            admin_chat_id = keys_list[0]
            if isinstance(admin_chat_id, str):
                try:
                    admin_chat_id = int(admin_chat_id)
                except ValueError:
                    pass
            try:
                test_msg = await bot.send_message(
                    user_id=admin_chat_id,
                    text="✅ Бот запущен и готов к работе!"
                )
                await bot.delete_message(chat_id=admin_chat_id, message_id=test_msg.message_id)
                print(f"✅ ADMIN_ID ({admin_chat_id}) - OK")
            except Exception as e:
                print(f"❌ ADMIN_ID ({admin_chat_id}) - ОШИБКА: {e}")
                print(f"   Проверьте, что ADMIN_ID правильный и бот может отправлять вам сообщения")
        else:
            print("❌ ADMIN_ID не найден!")
    except Exception as e:
        print(f"❌ Ошибка при проверке ADMIN_ID: {e}")
    
    # Проверка GROUP_ID удалена - заказы отправляются администраторам
    
    print("="*50 + "\n")
    
    # Добавляем глобальный обработчик ошибок
    @dp.errors()
    async def errors_handler(update: types.Update, exception: Exception):
        """Глобальный обработчик ошибок"""
        try:
            print(f"❌ Произошла ошибка: {exception}")
            if update and update.message:
                # Создаем FSMContext для обработки ошибок
                storage_key = StorageKey(
                    chat_id=update.message.chat.id,
                    user_id=update.message.from_user.id,
                    bot_id=None
                )
                user_state = FSMContext(storage=dp.storage, key=storage_key)
                await handle_unknown_message(update.message, user_state)
            elif update and update.callback_query:
                await update.callback_query.answer("Произошла ошибка. Попробуйте перезапустить бота.", show_alert=True)
        except Exception as e:
            print(f"❌ Ошибка в обработчике ошибок: {e}")
        return True  # Подавляем ошибку, чтобы бот продолжал работать
    
    dp.include_routers(form_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        pass
