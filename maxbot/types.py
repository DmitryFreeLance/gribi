from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class User:
    id: int
    username: Optional[str] = None
    full_name: str = ""


@dataclass
class Chat:
    id: int
    type: Optional[str] = None


class KeyboardButton:
    def __init__(self, text: str, payload: Optional[str] = None):
        self.text = text
        self.payload = payload


class ReplyKeyboardMarkup:
    def __init__(self, keyboard: List[List[KeyboardButton]], resize_keyboard: bool = True):
        self.keyboard = keyboard
        self.resize_keyboard = resize_keyboard


class InlineKeyboardButton:
    def __init__(self, text: str, callback_data: Optional[str] = None, url: Optional[str] = None):
        self.text = text
        self.callback_data = callback_data
        self.url = url


class InlineKeyboardMarkup:
    def __init__(self, inline_keyboard: List[List[InlineKeyboardButton]]):
        self.inline_keyboard = inline_keyboard


class BufferedInputFile:
    def __init__(self, data: bytes, filename: str = "file"):
        self.data = data
        self.filename = filename


class FSInputFile:
    def __init__(self, path: str):
        self.path = path

    def read(self) -> bytes:
        with open(self.path, "rb") as f:
            return f.read()


class URLInputFile:
    def __init__(self, url: str):
        self.url = url


class Message:
    def __init__(self, bot, message_id: str, chat: Chat, from_user: User, text: Optional[str], attachments: Optional[list] = None):
        self.bot = bot
        self.message_id = message_id
        self.chat = chat
        self.from_user = from_user
        self.text = text
        self.attachments = attachments or []

    async def answer(self, text: str, reply_markup=None, parse_mode: Optional[str] = None):
        return await self.bot.send_message(
            user_id=self.from_user.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    async def answer_photo(self, photo, caption: Optional[str] = None, reply_markup=None, parse_mode: Optional[str] = None):
        return await self.bot.send_photo(
            chat_id=None,
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            user_id=self.from_user.id,
        )

    async def delete(self):
        return await self.bot.delete_message(message_id=self.message_id)

    async def edit_text(self, text: str, reply_markup=None, parse_mode: Optional[str] = None):
        return await self.bot.edit_message_text(
            message_id=self.message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            existing_attachments=self.attachments,
        )

    async def edit_reply_markup(self, reply_markup=None):
        return await self.bot.edit_message_reply_markup(
            message_id=self.message_id,
            reply_markup=reply_markup,
            existing_attachments=self.attachments,
        )


class CallbackQuery:
    def __init__(self, bot, callback_id: str, from_user: User, message: Message, data: Optional[str]):
        self.bot = bot
        self.id = callback_id
        self.from_user = from_user
        self.message = message
        self.data = data

    async def answer(self, text: Optional[str] = None, show_alert: bool = False):
        # Max API supports only notification text; show_alert is ignored.
        return await self.bot.answer_callback(callback_id=self.id, text=text)


@dataclass
class Update:
    message: Optional[Message] = None
    callback_query: Optional[CallbackQuery] = None
