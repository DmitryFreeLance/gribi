# from aiogram.fsm.state import State, StatesGroup
# from aiogram import types, Dispatcher
# from constant import save_product_to_db
# from create_bot import bot, dp, admin_id
# from aiogram.fsm.context import FSMContext
#
#
# class ProfileStatesGroup(StatesGroup):
#     name_product_add = State()
#     price = State()
#     weight = State()
#     category = State()
#     photo = State()
#     des = State()
#
#
# async def command_add_product_start(message: types.Message):
#     if str(message.chat.id) in admin_id:  # Убедитесь, что переменная admin_id импортирована или перенесена
#         await ProfileStatesGroup.name_product_add.set()
#         await message.reply("Введите название товара:")
#     else:
#         await message.reply("У вас нет прав на это")
#
#
# async def process_name_add(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         data['name'] = message.text
#     await ProfileStatesGroup.des.set()
#     await message.reply("Введите описание товара")
#
#
# async def desk_add(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         data['des'] = message.text
#     await ProfileStatesGroup.price.set()
#     await message.reply("Введите цену товара:")
#
#
# async def process_price(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         data['price'] = message.text
#         await ProfileStatesGroup.category.set()
#     await message.reply(
#         "Введите котегорию товара:\nСуществующие категории\n1)Рапэ\n2)Шляпки\n3)Крема\n4)Целый гриб\n5)Капсулы\n6)Молотые\n7)Мази\n8)Чай\n9)Разное\n10)Благовония")
#
#
# async def process_category(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         data['category'] = message.text
#     await ProfileStatesGroup.weight.set()
#     await message.reply("Введите вес товара:")
#
#
# async def process_weight(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         data['weight'] = message.text
#     await ProfileStatesGroup.photo.set()
#     await message.reply("Загрузите фотографию товара:")
#
#
# async def process_photo(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         # Сохраняем файл фото
#         photo_id = message.photo[-1].file_id
#         file_info = await bot.get_file(photo_id)  # Убедитесь, что переменная bot импортирована или перенесена
#         downloaded_file = await bot.download_file(file_info.file_path)
#         file_path = f"images/{photo_id}.jpg"
#         with open(file_path, 'wb') as new_file:
#             new_file.write(downloaded_file.getvalue())
#         data['photo'] = file_path
#     await state.finish()
#     # Сохраняем информацию о товаре в базу данных SQLite
#
#     await save_product_to_db(data)  # Убедитесь, что функция save_product_to_db импортирована или перенесена
#
#     await message.reply(f"Товар добавлен:\n"
#                         f"Наименование: {data['name']}\n"
#                         f"Описание: {data['des']}\n"
#                         f"Цена: {data['price']}\n"
#                         f"Категория товара: {data['category']}\n"
#                         f"Вес в гр: {data['weight']}\n")
#
#     photo = types.InputFile(data["photo"])
#     await bot.send_message(chat_id=message.chat.id, text='Фото товара')
#     await bot.send_photo(chat_id=message.chat.id, photo=photo)
#
#
# def register_handlers_product(dp: Dispatcher):
#     dp.register_message_handler(process_name_add, state=ProfileStatesGroup.name_product_add)
#     dp.register_message_handler(desk_add, state=ProfileStatesGroup.des)
#     dp.register_message_handler(process_price, state=ProfileStatesGroup.price)
#     dp.register_message_handler(process_category, state=ProfileStatesGroup.category)
#     dp.register_message_handler(process_weight, state=ProfileStatesGroup.weight)
#     dp.register_message_handler(process_photo, content_types=['photo'], state=ProfileStatesGroup.photo)
