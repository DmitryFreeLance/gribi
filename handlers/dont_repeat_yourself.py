from maxbot import types
from constant import get_basket_for_user, get_basket_info_product_by_id, create_order
from ui import inline_menu
from create_bot import ProfileStatesGroup, bot, admin_id


async def categories(message, answer_text):
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
    await message.answer(answer_text, reply_markup=keyboard, parse_mode='html')


async def show_basket(message, state):
    """Единая функция для отображения корзины"""
    # Получаем ID пользователя из message
    user_id = message.from_user.id if hasattr(message, 'from_user') else message.chat.id
    user_products = await get_basket_for_user(user_id)
    if len(user_products) > 0:
        total_sum = 0
        
        # Выводим каждый товар отдельным сообщением с кнопкой удаления
        for i, (product_id, product, count) in enumerate(user_products, 1):
            product_info = await get_basket_info_product_by_id(product_id)
            if not product_info or len(product_info) == 0:
                # Если товар не найден, используем базовую информацию
                product_text = (
                    f"📦 <b>Товар {i}</b>\n\n"
                    f"<b>{product}</b>\n"
                    f"Количество: {count} шт\n"
                )
                # Создаем inline кнопку для удаления
                inline_kb = [
                    [types.InlineKeyboardButton(text="🗑 Удалить из корзины", callback_data=f"remove_from_basket_{product_id}")]
                ]
                inline_keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_kb)
                await message.answer(product_text, parse_mode='html', reply_markup=inline_keyboard)
                continue
            
            price_per_item = int(str(product_info[0][3]).replace("₽", ""))
            total_price = price_per_item * count
            total_sum += total_price
            
            product_text = (
                f"📦 <b>Товар {i}</b>\n\n"
                f"<b>{product}</b>\n"
                f"Количество: {count} шт\n"
                f"Вес: {product_info[0][2]}⚖\n"
                f"Цена за единицу: {product_info[0][3]}\n"
                f"<b>Общая цена: {total_price}₽</b>"
            )
            
            # Создаем inline кнопку для удаления
            inline_kb = [
                [types.InlineKeyboardButton(text="🗑 Удалить из корзины", callback_data=f"remove_from_basket_{product_id}")]
            ]
            inline_keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_kb)
            await message.answer(product_text, parse_mode='html', reply_markup=inline_keyboard)
        
        # Выводим общую сумму корзины
        total_message = (
            f"💰 <b>Итого в корзине:</b>\n\n"
            f"<b>Общая сумма: {total_sum}₽</b>"
        )
        
        # Кнопки для действий с корзиной
        kd = [
            [types.KeyboardButton(text=f"🗑 Очистить корзину")],
            [types.KeyboardButton(text=f"Вернуться в меню категорий ⬅"),
             types.KeyboardButton(text=f"☑ Оплатить корзину")],
        ]
        keyboard = inline_menu(kd)
        await message.answer(total_message, parse_mode='html', reply_markup=keyboard)
        await state.set_state(ProfileStatesGroup.basket_menu)
        return True
    else:
        await categories(message, answer_text="<code>У вас еще нет выбранных товаров 😔</code>")
        await state.set_state(ProfileStatesGroup.categories)
        return False


async def send_order_to_admins(
    user_id: int,
    username: str,
    payment_method: str,
    delivery_type: str,
    address: str,
    total_price: int,
    order_id: int = None
):
    """
    Отправляет заказ администраторам с кнопками подтверждения и отмены
    
    Args:
        user_id: ID пользователя
        username: Имя пользователя
        payment_method: Способ оплаты
        delivery_type: Тип доставки
        address: Адрес доставки
        total_price: Общая сумма заказа
        order_id: Уникальный ID заказа (если не указан, создается новый заказ в БД)
    
    Returns:
        tuple: (sent_messages, order_id) - список отправленных сообщений и ID заказа
    """
    from datetime import datetime
    
    # Создаем заказ в базе данных, если order_id не указан
    if order_id is None:
        order_id = await create_order(
            user_id=user_id,
            username=username,
            payment_method=payment_method,
            delivery_type=delivery_type,
            address=address,
            total_price=total_price
        )
        if order_id is None:
            # Если не удалось создать заказ, используем временный ID
            import time
            order_id = f"{user_id}_{int(time.time())}"
            print(f"⚠️ Использован временный ID заказа: {order_id}")
    
    # Получаем товары из корзины
    user_products = await get_basket_for_user(user_id)
    korzina = []
    for i, (product_id, product, count) in enumerate(user_products, 1):
        products_str = f"{i}) {product} {count} шт\n"
        product_info = await get_basket_info_product_by_id(product_id)
        if not product_info or len(product_info) == 0:
            korzina.append(f"{products_str}Товар: {product}, Количество: {count} шт")
            continue
        price = int(str(product_info[0][3]).replace("₽", "")) * count
        korzina.append(f"{products_str}Цена: {price}💵 Вес: {product_info[0][2]}⚖")
    korzina_str = "\n".join(korzina)
    
    # Формируем текст сообщения
    # Преобразуем order_id в строку для отображения (добавляем # для числовых ID)
    if isinstance(order_id, int):
        order_id_display = f"#{order_id}"
    else:
        order_id_display = str(order_id)
    
    order_text = (
        f"📦 <b>НОВЫЙ ЗАКАЗ</b>\n\n"
        f"🆔 ID заказа: <code>{order_id_display}</code>\n"
        f"👤 Пользователь: <code>{user_id}</code>\n"
        f"📱 @{username}\n\n"
        f"💳 Способ оплаты: {payment_method}\n"
        f"🚚 Доставка: {delivery_type}\n"
        f"💰 Сумма: {total_price} ₽\n\n"
        f"📋 <b>Состав заказа:</b>\n{korzina_str}\n\n"
    )
    
    if address:
        order_text += f"📍 <b>Адрес доставки:</b>\n{address}\n\n"
    
    order_text += f"🕐 Время заказа: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    
    # Создаем inline кнопки
    inline_kb = [
        [
            types.InlineKeyboardButton(
                text="✅ Подтвердить заказ",
                callback_data=f"confirm_order_{order_id}"
            ),
            types.InlineKeyboardButton(
                text="❌ Отмена заказа",
                callback_data=f"cancel_order_{order_id}"
            )
        ]
    ]
    inline_keyboard = types.InlineKeyboardMarkup(inline_keyboard=inline_kb)
    
    # Отправляем сообщение администраторам
    try:
        sent_messages = []
        for admin_chat_id in admin_id.keys():
            chat_id = admin_chat_id
            if isinstance(chat_id, str):
                try:
                    chat_id = int(chat_id)
                except ValueError:
                    pass
            print(f"📤 Попытка отправить заказ админу с ID: {chat_id}")
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=order_text,
                parse_mode='HTML',
                reply_markup=inline_keyboard
            )
            sent_messages.append(sent_message)
        print("✅ Заказ успешно отправлен администраторам!")
        return sent_messages, order_id
    except Exception as e:
        import traceback
        print(f"❌ Ошибка при отправке заказа администраторам: {e}")
        traceback.print_exc()
        return None, order_id
