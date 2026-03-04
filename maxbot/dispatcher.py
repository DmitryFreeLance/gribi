import asyncio
from typing import Any, Awaitable, Callable, List, Optional, Tuple

from .filters import BaseFilter
from .fsm import FSMContext, StorageKey, State
from .types import CallbackQuery, Message, Update, User, Chat

Handler = Callable[..., Awaitable[Any]]


class Router:
    def __init__(self):
        self.message_handlers: List[Tuple[Tuple[Any, ...], Handler]] = []
        self.callback_handlers: List[Tuple[Tuple[Any, ...], Handler]] = []

    def message(self, *filters):
        def decorator(func: Handler):
            self.message_handlers.append((filters, func))
            return func
        return decorator

    def callback_query(self, *filters):
        def decorator(func: Handler):
            self.callback_handlers.append((filters, func))
            return func
        return decorator


class Dispatcher:
    def __init__(self, storage):
        self.storage = storage
        self.routers: List[Router] = []
        self.error_handlers: List[Handler] = []

    def include_routers(self, *routers: Router):
        self.routers.extend(routers)

    def errors(self):
        def decorator(func: Handler):
            self.error_handlers.append(func)
            return func
        return decorator

    async def start_polling(self, bot):
        marker = None
        while True:
            try:
                updates = await bot.get_updates(marker=marker, limit=100, timeout=30,
                                                types_list=["message_created", "message_callback", "bot_started"])
                marker = updates.get("marker", marker)
                for update in updates.get("updates", []):
                    await self._process_update(bot, update)
            except Exception as exc:
                print(f"❌ Ошибка при получении обновлений: {exc}")
                await asyncio.sleep(2)

    async def _process_update(self, bot, update_data: dict):
        update_type = update_data.get("update_type")
        if update_type == "message_created":
            message = self._message_from_update(bot, update_data.get("message"))
            if not message:
                return
            state = FSMContext(storage=self.storage, key=StorageKey(chat_id=message.chat.id, user_id=message.from_user.id, bot_id=None))
            update = Update(message=message)
            await self._dispatch_message(message, state, update)
        elif update_type == "message_callback":
            callback = update_data.get("callback") or {}
            message = self._message_from_update(bot, update_data.get("message"))
            if not message:
                return
            user = self._user_from_sender(callback.get("user") or {})
            cb = CallbackQuery(
                bot=bot,
                callback_id=callback.get("callback_id"),
                from_user=user,
                message=message,
                data=callback.get("payload"),
            )
            state = FSMContext(storage=self.storage, key=StorageKey(chat_id=message.chat.id, user_id=user.id, bot_id=None))
            update = Update(callback_query=cb)
            await self._dispatch_callback(cb, state, update)
        elif update_type == "bot_started":
            user = self._user_from_sender(update_data.get("user") or {})
            chat = Chat(id=user.id)
            message = Message(bot=bot, message_id="", chat=chat, from_user=user, text="/start", attachments=[])
            state = FSMContext(storage=self.storage, key=StorageKey(chat_id=chat.id, user_id=user.id, bot_id=None))
            update = Update(message=message)
            await self._dispatch_message(message, state, update)

    async def _dispatch_message(self, message: Message, state: FSMContext, update: Update):
        for router in self.routers:
            for filters, handler in router.message_handlers:
                if await self._match_filters(filters, message, state):
                    try:
                        await handler(message, state)
                    except Exception as exc:
                        await self._handle_error(update, exc)
                    return

    async def _dispatch_callback(self, callback: CallbackQuery, state: FSMContext, update: Update):
        if callback.data and isinstance(callback.data, str) and callback.data.startswith("menu:"):
            # Make menu callbacks behave like user messages.
            callback.message.text = callback.data.split("menu:", 1)[1]
            callback.message.from_user = callback.from_user
            callback.message.chat.id = callback.from_user.id
            try:
                await callback.answer()
            except Exception:
                pass
            await self._dispatch_message(callback.message, state, Update(message=callback.message))
            return
        for router in self.routers:
            for filters, handler in router.callback_handlers:
                if await self._match_filters(filters, callback, state):
                    try:
                        await handler(callback, state)
                    except Exception as exc:
                        await self._handle_error(update, exc)
                    return

    async def _match_filters(self, filters: Tuple[Any, ...], obj: Any, state: FSMContext) -> bool:
        for filt in filters:
            if isinstance(filt, State):
                current = await state.get_state()
                if current != filt.name:
                    return False
            elif isinstance(filt, BaseFilter):
                if not filt(obj):
                    return False
            elif callable(filt):
                if not filt(obj):
                    return False
        return True

    async def _handle_error(self, update: Update, exc: Exception):
        if not self.error_handlers:
            print(f"❌ Ошибка обработки: {exc}")
            return
        for handler in self.error_handlers:
            try:
                await handler(update, exc)
            except Exception as inner_exc:
                print(f"❌ Ошибка в обработчике ошибок: {inner_exc}")

    def _user_from_sender(self, sender: dict) -> User:
        user_id = sender.get("user_id") or sender.get("id") or 0
        username = sender.get("username")
        full_name = sender.get("name") or sender.get("full_name") or ""
        return User(id=int(user_id), username=username, full_name=full_name)

    def _message_from_update(self, bot, message_data: Optional[dict]) -> Optional[Message]:
        if not message_data:
            return None
        body = message_data.get("body", {})
        sender = message_data.get("sender", {})
        recipient = message_data.get("recipient", {})
        text = body.get("text")
        attachments = body.get("attachments") or []
        if text is None:
            for att in attachments:
                if att.get("type") == "data":
                    payload = att.get("data")
                    if isinstance(payload, str):
                        text = payload
                        break
        user = self._user_from_sender(sender)
        # For private chats, reply should go to sender user_id.
        chat = Chat(id=int(user.id))
        return Message(
            bot=bot,
            message_id=str(body.get("mid")),
            chat=chat,
            from_user=user,
            text=text,
            attachments=attachments,
        )
