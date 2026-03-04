# Словарь для соответствия текста сообщения эмодзи и названий товаров в базе данных
import sqlite3
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем имя базы данных из переменных окружения
DATABASE_NAME = os.getenv('DATABASE_NAME', 'sqlite_python.db')
DEFAULT_DB_PATH = os.getenv('DEFAULT_DB_PATH', 'sqlite_python.db')


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _create_list_gribs_table(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS list_gribs
            (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                wt TEXT NOT NULL,
                cash INT NOT NULL,
                topic TEXT NOT NULL,
                photo TEXT NULL,
                description TEXT NULL
            )
        ''')
        conn.commit()
    finally:
        conn.close()


async def ensure_database():
    '''Ensure DB file exists and core tables are created.

    If DATABASE_NAME does not exist, try to seed it from DEFAULT_DB_PATH.
    '''
    db_path = Path(DATABASE_NAME)
    if not db_path.exists() or db_path.stat().st_size == 0:
        default_path = Path(DEFAULT_DB_PATH)
        if default_path.exists() and default_path.resolve() != db_path.resolve():
            _ensure_dir(db_path)
            shutil.copyfile(str(default_path), str(db_path))
            print(f"✅ База данных скопирована из {default_path} в {db_path}")
        else:
            _ensure_dir(db_path)
            _create_list_gribs_table(db_path)
            print(f"✅ Создана новая база данных {db_path}")
    else:
        _create_list_gribs_table(db_path)

    # Гарантируем наличие служебных таблиц
    await create_database_accurately()
    await create_orders_table()

emojis_to_topics = {
    "🌿 Рапэ племенное": "Рапэ",
    "🍄 Мухоморы  шляпки": "Шляпки",
    "🍄 Мухоморные крема": "Крема",
    "🦔 Цельный гриб": "Целый гриб",
    "💊 Микродозинг в капсулах": "Капуслы",
    "⭐ Молотый": "Молотые",
    "🥤 Настойки": "Настойки",
    "🥥 Мази": "Мази",
    "🌱 Чай": "Чай",
    "💧 Капли для глаз": "Капли",
    "⚜ Благовония": "Благовония",
    "📑 Разное": "Разное",
}


# Функция для добавления товара в корзину (обновляет количество если товар уже есть)
async def add_to_basket(user_id: int, product_id: int, product: str, counnt: int):
    try:
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()

        # Проверяем, существует ли таблица basket с новыми полями
        cursor.execute('''CREATE TABLE IF NOT EXISTS basket (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            product_id INTEGER,
                            product TEXT,
                            counnt INTEGER
                          )''')

        # Добавляем поле product_id если его нет (миграция)
        try:
            cursor.execute("ALTER TABLE basket ADD COLUMN product_id INTEGER")
        except sqlite3.OperationalError:
            pass  # Колонка уже существует

        # Проверяем, есть ли уже этот товар в корзине пользователя
        cursor.execute("SELECT id, counnt FROM basket WHERE user_id=? AND product_id=?", (user_id, product_id))
        existing = cursor.fetchone()

        if existing:
            # Обновляем количество существующего товара
            new_count = existing[1] + counnt
            cursor.execute("UPDATE basket SET counnt=? WHERE id=?", (new_count, existing[0]))
            print(f"Количество товара обновлено: {new_count} шт")
        else:
            # Добавляем новый товар в корзину
            cursor.execute("INSERT INTO basket (user_id, product_id, product, counnt) VALUES (?, ?, ?, ?)", 
                         (user_id, product_id, product, counnt))
            print("Товар успешно добавлен в корзину.")

        sqlite_connection.commit()
    except sqlite3.Error as error:
        print("Ошибка при добавлении товара в корзину:", error)
    finally:
        if sqlite_connection:
            sqlite_connection.close()


# Отчиста корзины у пользователя
async def clear_basket(user_id: int):
    try:
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()

        # Удаляем товары из корзины для указанного пользователя
        cursor.execute("DELETE FROM basket WHERE user_id = ?", (user_id,))
        sqlite_connection.commit()

    except sqlite3.Error as error:
        print("Ошибка при работе с SQLite:", error)

    finally:
        if sqlite_connection:
            sqlite_connection.close()

# Функция для получения товаров из корзины для определенного пользователя
async def get_basket_for_user(user_id: int):
    try:
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()
        
        # Проверяем, есть ли колонка product_id
        cursor.execute("PRAGMA table_info(basket)")
        columns = [column[1] for column in cursor.fetchall()]
        has_product_id = 'product_id' in columns
        
        if has_product_id:
            # Мигрируем старые записи без product_id
            cursor.execute("SELECT id, product FROM basket WHERE user_id=? AND product_id IS NULL", (user_id,))
            old_products = cursor.fetchall()
            for old_id, product_name in old_products:
                # Получаем product_id по имени товара
                cursor.execute("SELECT id FROM list_gribs WHERE name=?", (product_name,))
                product_info = cursor.fetchone()
                if product_info:
                    product_id = product_info[0]
                    cursor.execute("UPDATE basket SET product_id=? WHERE id=?", (product_id, old_id))
                    sqlite_connection.commit()
            
            # Проверяем, есть ли дубликаты (несколько записей с одинаковым product_id)
            cursor.execute("""
                SELECT product_id, COUNT(*) as cnt 
                FROM basket 
                WHERE user_id=? AND product_id IS NOT NULL
                GROUP BY product_id
                HAVING cnt > 1
            """, (user_id,))
            duplicates = cursor.fetchall()
            
            # Обновляем базу данных только если есть дубликаты
            if duplicates:
                # Получаем товары с группировкой по product_id и суммированием количества
                cursor.execute("""
                    SELECT product_id, 
                           MAX(product) as product, 
                           SUM(counnt) as total_count 
                    FROM basket 
                    WHERE user_id=? AND product_id IS NOT NULL
                    GROUP BY product_id
                """, (user_id,))
                grouped_products = cursor.fetchall()
                
                for product_id, product_name, total_count in grouped_products:
                    # Удаляем все записи для этого товара
                    cursor.execute("DELETE FROM basket WHERE user_id=? AND product_id=?", (user_id, product_id))
                    # Создаем одну запись с правильным количеством
                    cursor.execute("INSERT INTO basket (user_id, product_id, product, counnt) VALUES (?, ?, ?, ?)",
                                 (user_id, product_id, product_name, total_count))
                sqlite_connection.commit()
            
            # Получаем финальные данные (без пересоздания, если дубликатов нет)
            cursor.execute("SELECT product_id, product, counnt FROM basket WHERE user_id=? AND product_id IS NOT NULL", (user_id,))
            products = cursor.fetchall()
        else:
            # Старая версия базы - получаем только product и counnt, затем мигрируем
            cursor.execute("SELECT product, counnt FROM basket WHERE user_id=?", (user_id,))
            old_products = cursor.fetchall()
            # Добавляем колонку product_id
            try:
                cursor.execute("ALTER TABLE basket ADD COLUMN product_id INTEGER")
                sqlite_connection.commit()
            except sqlite3.OperationalError:
                pass
            
            # Мигрируем данные
            products = []
            for product_name, count in old_products:
                cursor.execute("SELECT id FROM list_gribs WHERE name=?", (product_name,))
                product_info = cursor.fetchone()
                if product_info:
                    product_id = product_info[0]
                    cursor.execute("UPDATE basket SET product_id=? WHERE product=? AND user_id=?", 
                                 (product_id, product_name, user_id))
                    products.append((product_id, product_name, count))
            sqlite_connection.commit()
            
            # Если миграция прошла успешно, получаем данные заново
            if products:
                cursor.execute("SELECT product_id, product, counnt FROM basket WHERE user_id=?", (user_id,))
                products = cursor.fetchall()
        
        return products  # Возвращаем список товаров пользователя (product_id, product, counnt)
    except sqlite3.Error as error:
        print("Ошибка при получении товаров из корзины:", error)
        return []
    finally:
        if sqlite_connection:
            sqlite_connection.close()


async def get_basket_info_product(name_product: str):
    sqlite_connection = sqlite3.connect(DATABASE_NAME)
    cursor = sqlite_connection.cursor()
    cursor.execute("SELECT * FROM list_gribs WHERE name=?", (name_product,))
    records = cursor.fetchall()
    return records

async def get_basket_info_product_by_id(product_id: int):
    sqlite_connection = sqlite3.connect(DATABASE_NAME)
    cursor = sqlite_connection.cursor()
    cursor.execute("SELECT * FROM list_gribs WHERE id=?", (product_id,))
    records = cursor.fetchall()
    return records


async def get_basket_info_all():
    sqlite_connection = sqlite3.connect(DATABASE_NAME)
    cursor = sqlite_connection.cursor()
    cursor.execute("SELECT * FROM basket")
    records = cursor.fetchall()
    return records


# Функция для удаления всех строк корзины пользователя по его user_id
async def delete_basket_for_user(user_id: int):
    try:
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()
        cursor.execute("DELETE FROM basket WHERE user_id=?", (user_id,))
        sqlite_connection.commit()
    except sqlite3.Error as error:
        print("Ошибка при удалении товаров из корзины:", error)
    finally:
        if sqlite_connection:
            sqlite_connection.close()


# Функция для удаления определенного товара в бд по user_id и product_id
async def delete_product_for_user(user_id, product_id, counnt: int):
    try:
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()
        # Получаем все записи для этого товара (на случай дубликатов)
        cursor.execute("SELECT id, counnt FROM basket WHERE user_id=? AND product_id=?",
                       (user_id, product_id))
        existing_records = cursor.fetchall()

        if existing_records:
            # Если есть несколько записей, суммируем количество
            total_count = sum(record[1] for record in existing_records)
            new_count = total_count - counnt
            
            if new_count <= 0:
                # Удаляем все записи товара полностью
                cursor.execute("DELETE FROM basket WHERE user_id=? AND product_id=?", (user_id, product_id))
            else:
                # Получаем название товара ДО удаления
                cursor.execute("SELECT product FROM basket WHERE user_id=? AND product_id=? LIMIT 1", (user_id, product_id))
                product_name_record = cursor.fetchone()
                product_name = "Товар"
                if product_name_record:
                    product_name = product_name_record[0]
                else:
                    # Получаем название из list_gribs
                    cursor.execute("SELECT name FROM list_gribs WHERE id=?", (product_id,))
                    product_info = cursor.fetchone()
                    if product_info:
                        product_name = product_info[0]
                
                # Удаляем все записи
                cursor.execute("DELETE FROM basket WHERE user_id=? AND product_id=?", (user_id, product_id))
                # Создаем одну запись с правильным количеством
                cursor.execute("INSERT INTO basket (user_id, product_id, product, counnt) VALUES (?, ?, ?, ?)",
                             (user_id, product_id, product_name, new_count))
            sqlite_connection.commit()
        else:
            print("Не найдено товаров для удаления с указанными условиями.")
    except sqlite3.Error as error:
        print("Ошибка при удалении товара из корзины:", error)
    finally:
        if sqlite_connection:
            sqlite_connection.close()


async def save_product_to_db(product_info):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO list_gribs (name, wt, cash, topic, photo, description) VALUES (?, ?, ?, ?, ?, ?)",
                  (product_info['name'], product_info['weight'], product_info['price'],
                   product_info['category'], product_info['photo'], product_info['des']))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Ошибка при выполнении SQL-запроса: {e}")
    finally:
        conn.close()


async def delete_product_to_db(product_info):
    sqlite_connection = sqlite3.connect(DATABASE_NAME)
    cursor = sqlite_connection.cursor()

    # Выполняем SQL-запрос DELETE для удаления записи по имени товара
    cursor.execute("DELETE FROM list_gribs WHERE name=?", (product_info,))

    # Подтверждаем изменения в базе данных
    sqlite_connection.commit()

    # Возвращаем True, если удаление прошло успешно
    return True


async def update_product_in_db(updated_info):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()

    # Формируем запрос SQL для обновления информации о товаре
    query = "UPDATE list_gribs SET "

    # Добавляем к запросу SQL каждый параметр для обновления
    if 'weight_edit' in updated_info:
        query += "wt = " + updated_info['weight_edit'] + ", "
    if 'price_edit' in updated_info:
        query += "cash = '" + updated_info['price_edit'] + "', "
    if 'category_edit' in updated_info:
        query += "topic = '" + updated_info['category_edit'] + "', "
    if 'photo_edit' in updated_info:
        query += "photo = '" + updated_info['photo_edit'] + "', "
    if 'des_edit' in updated_info:
        query += "description = '" + updated_info['des_edit'] + "', "
    # Удаляем последнюю запятую и пробел в запросе
    query = query[:-2]

    # # Добавляем условие WHERE для выборки конкретного товара по его имени
    query += " WHERE name = '" + updated_info['name_edit'] + "'"
    # Выполняем запрос
    c.execute(query)

    conn.commit()
    conn.close()


async def add_to_address(user_id: int, address, type_a: str):
    try:
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()

        # Проверяем, существует ли таблица address
        cursor.execute('''CREATE TABLE IF NOT EXISTS address (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            address TEXT,
                            type_a TEXT
                          )''')

        # Добавляем товар в корзину
        cursor.execute("INSERT INTO address (user_id, address, type_a) VALUES (?, ?, ?)", (user_id, address, type_a))
        sqlite_connection.commit()

    except sqlite3.Error as error:
        print("Ошибка при добавлении товара в корзину:", error)
    finally:
        if sqlite_connection:
            sqlite_connection.close()


async def get_address_for_user(user_id: int, type_a: str):
    sqlite_connection = sqlite3.connect(DATABASE_NAME)
    cursor = sqlite_connection.cursor()
    cursor.execute("SELECT address, type_a FROM address WHERE user_id=? AND type_a=?", (user_id, type_a))
    records = cursor.fetchall()
    return records


async def search_address_in_user(address, type_a: str):
    sqlite_connection = sqlite3.connect(DATABASE_NAME)
    cursor = sqlite_connection.cursor()
    cursor.execute("SELECT address FROM address WHERE address=? AND type_a=?", (address, type_a))
    records = cursor.fetchall()
    return records


async def search_address_in_user_BCE(user_id: int):
    sqlite_connection = sqlite3.connect(DATABASE_NAME)
    cursor = sqlite_connection.cursor()
    cursor.execute("SELECT address FROM address WHERE user_id=?", (user_id,))
    address_user = cursor.fetchall()
    return address_user


async def search_BCE(address: str):
    sqlite_connection = sqlite3.connect(DATABASE_NAME)
    cursor = sqlite_connection.cursor()
    cursor.execute("SELECT address, type_a FROM address WHERE address=?", (address,))
    res = cursor.fetchall()
    return res


async def create_database_accurately():
    # Подключение к базе данных (или её создание, если она не существует)
    conn = sqlite3.connect(DATABASE_NAME)
    # Создание объекта cursor, который позволяет выполнять SQL-запросы
    cursor = conn.cursor()

    # SQL-запрос для создания таблицы
    create_table_query = """
    CREATE TABLE IF NOT EXISTS accurately_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_client INTEGER,
        count INTEGER NOT NULL,
        product TEXT NOT NULL,
        accurately BOOLEAN NOT NULL CHECK (accurately IN (0, 1))
    );
    """

    # Выполнение SQL-запроса
    cursor.execute(create_table_query)

    # Закрытие соединения с базой данных
    conn.commit()
    conn.close()


async def get_database_accurately(id_client):
    # Подключение к базе данных
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Выполнение запроса
    cursor.execute('SELECT * FROM accurately_products WHERE ID_client=?', (id_client,))
    data = cursor.fetchall()  # Получаем все записи по ID

    conn.close()

    return data


async def add_order_accurately(ID_client, count, product, accurately):
    try:
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()

        # Проверяем, существует ли таблица address
        cursor.execute('''CREATE TABLE IF NOT EXISTS accurately_products (
                                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    ID_client INTEGER,
                                    count INTEGER NOT NULL,
                                    product TEXT NOT NULL,
                                    accurately BOOLEAN NOT NULL CHECK (accurately IN (0, 1))
                                  )''')

        # Добавляем товар в корзину
        cursor.execute("INSERT INTO accurately_products (ID_client, count, product, accurately) VALUES (?, ?, ?, ?)", (ID_client, count, product, accurately))
        sqlite_connection.commit()


    except sqlite3.Error as error:
        print("Ошибка при добавлении товара в корзину:", error)
    finally:
        if sqlite_connection:
            sqlite_connection.close()


# Функции для работы с заказами
async def create_orders_table():
    """Создает таблицу для хранения заказов"""
    try:
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            username TEXT,
                            payment_method TEXT,
                            delivery_type TEXT,
                            address TEXT,
                            total_price INTEGER,
                            status TEXT DEFAULT 'pending',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            confirmed_at TIMESTAMP,
                            cancelled_at TIMESTAMP,
                            cancel_reason TEXT,
                            cancelled_by INTEGER
                          )''')
        
        sqlite_connection.commit()
        print("✅ Таблица orders создана или уже существует")
    except sqlite3.Error as error:
        print(f"Ошибка при создании таблицы orders: {error}")
    finally:
        if sqlite_connection:
            sqlite_connection.close()


async def create_order(user_id: int, username: str, payment_method: str, delivery_type: str, 
                       address: str, total_price: int) -> int:
    """
    Создает новый заказ в базе данных и возвращает его ID
    
    Returns:
        int: ID созданного заказа
    """
    await create_orders_table()
    
    try:
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()
        
        cursor.execute('''INSERT INTO orders 
                         (user_id, username, payment_method, delivery_type, address, total_price, status)
                         VALUES (?, ?, ?, ?, ?, ?, 'pending')''',
                      (user_id, username, payment_method, delivery_type, address, total_price))
        
        order_id = cursor.lastrowid
        sqlite_connection.commit()
        
        print(f"✅ Заказ создан с ID: {order_id}")
        return order_id
    except sqlite3.Error as error:
        print(f"Ошибка при создании заказа: {error}")
        return None
    finally:
        if sqlite_connection:
            sqlite_connection.close()


async def get_order_by_id(order_id: int):
    """Получает информацию о заказе по его ID"""
    try:
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()
        
        cursor.execute('''SELECT * FROM orders WHERE order_id = ?''', (order_id,))
        order = cursor.fetchone()
        
        return order
    except sqlite3.Error as error:
        print(f"Ошибка при получении заказа: {error}")
        return None
    finally:
        if sqlite_connection:
            sqlite_connection.close()


async def update_order_status(order_id: int, status: str, **kwargs):
    """
    Обновляет статус заказа
    
    Args:
        order_id: ID заказа
        status: Новый статус ('pending', 'confirmed', 'cancelled')
        **kwargs: Дополнительные поля для обновления (confirmed_at, cancelled_at, cancel_reason, cancelled_by)
    """
    try:
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()
        
        update_fields = ['status = ?']
        values = [status]
        
        if 'confirmed_at' in kwargs:
            update_fields.append('confirmed_at = ?')
            values.append(kwargs['confirmed_at'])
        
        if 'cancelled_at' in kwargs:
            update_fields.append('cancelled_at = ?')
            values.append(kwargs['cancelled_at'])
        
        if 'cancel_reason' in kwargs:
            update_fields.append('cancel_reason = ?')
            values.append(kwargs['cancel_reason'])
        
        if 'cancelled_by' in kwargs:
            update_fields.append('cancelled_by = ?')
            values.append(kwargs['cancelled_by'])
        
        values.append(order_id)
        
        query = f"UPDATE orders SET {', '.join(update_fields)} WHERE order_id = ?"
        cursor.execute(query, values)
        
        sqlite_connection.commit()
        print(f"✅ Статус заказа {order_id} обновлен на {status}")
    except sqlite3.Error as error:
        print(f"Ошибка при обновлении статуса заказа: {error}")
    finally:
        if sqlite_connection:
            sqlite_connection.close()


async def get_user_orders(user_id: int):
    """Получает все заказы пользователя"""
    try:
        sqlite_connection = sqlite3.connect(DATABASE_NAME)
        cursor = sqlite_connection.cursor()
        
        cursor.execute('''SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC''', (user_id,))
        orders = cursor.fetchall()
        
        return orders
    except sqlite3.Error as error:
        print(f"Ошибка при получении заказов пользователя: {error}")
        return []
    finally:
        if sqlite_connection:
            sqlite_connection.close()
