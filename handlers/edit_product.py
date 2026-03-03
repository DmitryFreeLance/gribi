# from aiogram import types, Dispatcher
# from aiogram.dispatcher import FSMContext
# from aiogram.dispatcher.filters.state import State, StatesGroup
# from constant import update_product_in_db
# from create_bot import bot, admin_id
#
#
# class EditProductStatesGroup(StatesGroup):
#     name_product_edit = State()
#     edit_option = State()
#     price_edit = State()
#     category_edit = State()
#     weight_edit = State()
#     photo_edit = State()
#     des_edit = State()
#
#
# async def command_edit_product_start(message: types.Message):
#     if str(message.chat.id) in admin_id:
#         await EditProductStatesGroup.name_product_edit.set()
#         await message.reply("Введите название товара, который вы хотите отредактировать:")
#
#     else:
#         await message.reply("У вас нет прав на это")
#
#
# async def process_name_edit(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         data['name_edit'] = message.text
#
#     await EditProductStatesGroup.edit_option.set()
#     await message.reply("Выберите, что вы хотите отредактировать:\n"
#                         "1. Цену\n"
#                         "2. Категорию\n"
#                         "3. Вес\n"
#                         "4. Фото\n"
#                         "5. Описание")
#
#
# async def process_edit_option(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         edit_option = message.text.lower()
#
#         if edit_option == "цену":
#             await message.reply("Введите новую цену:")
#             await EditProductStatesGroup.price_edit.set()
#
#         elif edit_option == "категорию":
#             await message.reply("Введите новую категорию:")
#             await EditProductStatesGroup.category_edit.set()
#
#         elif edit_option == "вес":
#             await message.reply("Введите новый вес:")
#             await EditProductStatesGroup.weight_edit.set()
#
#         elif edit_option == "фото":
#             await message.reply("Пришлите новое фото товара:")
#             await EditProductStatesGroup.photo_edit.set()
#
#         elif edit_option == "описание":
#             await message.reply("Пришлите новое описание товара:")
#             await EditProductStatesGroup.des_edit.set()
#
#         else:
#             await message.reply("Неправильный вариант, выберите один из предложенных вариантов.")
#
#
# async def process_price_edit(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         data['price_edit'] = message.text
#
#     await update_product_info(message, state)
#
#
# async def process_category_edit(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         data['category_edit'] = message.text
#
#     await update_product_info(message, state)
#
#
# async def process_weight_edit(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         data['weight_edit'] = message.text
#
#     await update_product_info(message, state)
#
#
# async def process_des_edit(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         data['des_edit'] = message.text
#
#     await update_product_info(message, state)
#
#
# async def process_photo_edit(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         # Сохраняем новое фото
#         photo_id = message.photo[-1].file_id
#         file_info = await bot.get_file(photo_id)  # Убедитесь, что переменная bot импортирована или перенесена
#         downloaded_file = await bot.download_file(file_info.file_path)
#         file_path = f"images/{photo_id}.jpg"
#         with open(file_path, 'wb') as new_file:
#             new_file.write(downloaded_file.getvalue())
#         data['photo_edit'] = file_path
#
#     await update_product_info(message, state)
#
#
# async def update_product_info(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         # name_product = data['name']
#         # Сделать запрос в базу данных для обновления информации о товаре
#         # Например, вызов функции, которая обновляет информацию в базе данных
#         await update_product_in_db(data)
#
#     await state.finish()
#     await message.reply("Информация о товаре успешно обновлена.")
#
#
# def edit_handlers_product(dp: Dispatcher):
#     dp.register_message_handler(command_edit_product_start, commands=['edit_product'], state="*")
#     dp.register_message_handler(process_name_edit, state=EditProductStatesGroup.name_product_edit)
#     dp.register_message_handler(process_edit_option, state=EditProductStatesGroup.edit_option)
#     dp.register_message_handler(process_price_edit, state=EditProductStatesGroup.price_edit)
#     dp.register_message_handler(process_category_edit, state=EditProductStatesGroup.category_edit)
#     dp.register_message_handler(process_weight_edit, state=EditProductStatesGroup.weight_edit)
#     dp.register_message_handler(process_des_edit, state=EditProductStatesGroup.des_edit)
#     dp.register_message_handler(process_photo_edit, content_types=['photo'], state=EditProductStatesGroup.photo_edit)
