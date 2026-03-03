# from aiogram import types, Dispatcher
# from aiogram.dispatcher import FSMContext
# from aiogram.dispatcher.filters.state import State, StatesGroup
# from create_bot import admin_id
# from constant import delete_product_to_db
#
#
# class ProfileStatesGroup(StatesGroup):
#     name_product_del = State()
#     verification = State()
#     verification_finish = State()
#
#
# async def command_del_product_start(message: types.Message):
#     if str(message.chat.id) in admin_id:
#         await ProfileStatesGroup.verification.set()
#         await message.reply("Введите название товара:")
#     else:
#         await message.reply("У вас нет прав на это")
#
#
# async def process_verification(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         data['name'] = message.text
#     await ProfileStatesGroup.verification_finish.set()
#     await message.reply(
#         "Подвердите действие (да/нет):\nВнимание действие необратимо, товар невозможно будет восстановить")
#
#
# async def process_verification_finish(message: types.Message, state: FSMContext):
#     async with state.proxy() as data:
#         data['verification'] = message.text
#         verification = data.get('verification', '').lower()
#         verification_finish = message.text.lower()
#
#         if verification_finish == "да":
#             # Здесь должна быть логика удаления товара
#             await delete_product_to_db(str(data['name']))
#             await message.reply("Товар успешно удален.")
#             await state.finish()
#         elif verification_finish == "нет":
#             await message.reply("Удаление товара отменено.")
#             await state.finish()
#         else:
#             await message.reply("Пожалуйста, введите 'да' или 'нет'.")
#
#
# # def delete_handlers_product(dp: Dispatcher):
# #     dp.register_message_handler(command_del_product_start, commands=['del_product'], state="*")
# #     dp.register_message_handler(process_verification, state=ProfileStatesGroup.verification)
# #     dp.register_message_handler(process_verification_finish, state=ProfileStatesGroup.verification_finish)
