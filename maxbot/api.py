import aiohttp
import ssl
from typing import Any, Dict, List, Optional

from . import types


class MaxBot:
    def __init__(self, token: str, base_url: str = "https://platform-api.max.ru", api_version: Optional[str] = None,
                 session: Optional[aiohttp.ClientSession] = None, proxy_url: Optional[str] = None,
                 use_query_token: bool = False, ssl_verify: bool = True, trust_env: bool = True,
                 force_user_id: bool = True):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.proxy_url = proxy_url
        self.use_query_token = use_query_token
        self.ssl_verify = ssl_verify
        self.trust_env = trust_env
        self.force_user_id = force_user_id
        self.session = session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            ssl_ctx = ssl.create_default_context() if self.ssl_verify else False
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            self.session = aiohttp.ClientSession(connector=connector, trust_env=self.trust_env)
        return self.session

    def _auth_params(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = dict(params or {})
        if self.use_query_token:
            params["access_token"] = self.token
        if self.api_version:
            params["v"] = self.api_version
        return params

    def _auth_headers(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = dict(headers or {})
        # Dev docs use Authorization header; include it alongside query token for compatibility.
        headers.setdefault("Authorization", self.token)
        return headers

    async def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None,
                       json_data: Any = None, data: Any = None, headers: Optional[Dict[str, str]] = None) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        params = self._auth_params(params)
        headers = self._auth_headers(headers)
        session = await self._ensure_session()
        async with session.request(
            method,
            url,
            params=params,
            json=json_data,
            data=data,
            headers=headers,
            proxy=self.proxy_url,
        ) as resp:
            resp.raise_for_status()
            if resp.content_type == "application/json":
                return await resp.json()
            return await resp.text()

    async def get_updates(self, marker: Optional[int] = None, limit: int = 100, timeout: int = 30,
                          types_list: Optional[List[str]] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "timeout": timeout}
        if marker is not None:
            params["marker"] = marker
        if types_list:
            params["types"] = ",".join(types_list)
        return await self._request("GET", "/updates", params=params)

    def _format_from_parse_mode(self, parse_mode: Optional[str]) -> Optional[str]:
        if not parse_mode:
            return None
        mode = parse_mode.lower()
        if mode in ("html", "markdown"):
            return mode
        return None

    def _build_reply_keyboard_attachment(self, reply_markup: types.ReplyKeyboardMarkup) -> Dict[str, Any]:
        buttons: List[List[Dict[str, Any]]] = []
        for row in reply_markup.keyboard:
            row_buttons = []
            for button in row:
                payload = button.payload if button.payload is not None else button.text
                row_buttons.append({
                    "type": "message",
                    "text": button.text,
                    "payload": payload,
                })
            buttons.append(row_buttons)
        return {
            "type": "reply_keyboard",
            "buttons": buttons,
        }

    def _build_inline_keyboard_attachment(self, reply_markup: types.InlineKeyboardMarkup) -> Dict[str, Any]:
        buttons: List[List[Dict[str, Any]]] = []
        for row in reply_markup.inline_keyboard:
            row_buttons = []
            for button in row:
                if button.url:
                    row_buttons.append({
                        "type": "link",
                        "text": button.text,
                        "url": button.url,
                    })
                else:
                    row_buttons.append({
                        "type": "callback",
                        "text": button.text,
                        "payload": button.callback_data,
                    })
            buttons.append(row_buttons)
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": buttons,
            },
        }

    def _build_attachments(self, reply_markup=None, attachments: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        if attachments:
            result.extend(attachments)
        if isinstance(reply_markup, types.ReplyKeyboardMarkup):
            result.append(self._build_reply_keyboard_attachment(reply_markup))
        elif isinstance(reply_markup, types.InlineKeyboardMarkup):
            result.append(self._build_inline_keyboard_attachment(reply_markup))
        return result

    def _convert_existing_attachment(self, attachment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        att_type = attachment.get("type")
        if att_type in ("inline_keyboard", "reply_keyboard"):
            return None
        payload = attachment.get("payload") or {}
        if att_type == "image":
            if "token" in payload:
                payload = {"token": payload.get("token")}
            elif "url" in payload:
                payload = {"url": payload.get("url")}
            elif "photos" in payload:
                payload = {"photos": payload.get("photos")}
        return {"type": att_type, "payload": payload}

    def _rebuild_attachments_for_edit(self, existing_attachments: Optional[List[Dict[str, Any]]],
                                      reply_markup=None, remove_inline: bool = False) -> Optional[List[Dict[str, Any]]]:
        if existing_attachments is None and reply_markup is None:
            return None

        rebuilt: List[Dict[str, Any]] = []
        if existing_attachments:
            for att in existing_attachments:
                converted = self._convert_existing_attachment(att)
                if converted:
                    rebuilt.append(converted)
        if reply_markup is None and remove_inline:
            return rebuilt
        if isinstance(reply_markup, types.InlineKeyboardMarkup):
            rebuilt.append(self._build_inline_keyboard_attachment(reply_markup))
        elif isinstance(reply_markup, types.ReplyKeyboardMarkup):
            rebuilt.append(self._build_reply_keyboard_attachment(reply_markup))
        return rebuilt

    async def send_message(self, chat_id: Optional[int] = None, text: Optional[str] = None,
                           user_id: Optional[int] = None, reply_markup=None, parse_mode: Optional[str] = None,
                           attachments: Optional[List[Dict[str, Any]]] = None):
        body: Dict[str, Any] = {}
        if text is not None:
            body["text"] = text
        msg_format = self._format_from_parse_mode(parse_mode)
        if msg_format:
            body["format"] = msg_format
        final_attachments = self._build_attachments(reply_markup=reply_markup, attachments=attachments)
        if final_attachments:
            body["attachments"] = final_attachments
        params: Dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = user_id
        elif chat_id is not None:
            if self.force_user_id and chat_id > 0:
                params["user_id"] = chat_id
            else:
                params["chat_id"] = chat_id
        response = await self._request("POST", "/messages", params=params, json_data=body)
        return self._message_from_api(response.get("message"))

    async def edit_message_text(self, message_id: str, text: str, reply_markup=None,
                                parse_mode: Optional[str] = None, existing_attachments: Optional[List[Dict[str, Any]]] = None):
        body: Dict[str, Any] = {"text": text}
        msg_format = self._format_from_parse_mode(parse_mode)
        if msg_format:
            body["format"] = msg_format
        attachments = self._rebuild_attachments_for_edit(existing_attachments, reply_markup=reply_markup)
        if attachments is not None:
            body["attachments"] = attachments
        await self._request("PUT", "/messages", params={"message_id": message_id}, json_data=body)

    async def edit_message_reply_markup(self, message_id: str, reply_markup=None,
                                        existing_attachments: Optional[List[Dict[str, Any]]] = None):
        body: Dict[str, Any] = {}
        attachments = self._rebuild_attachments_for_edit(
            existing_attachments,
            reply_markup=reply_markup,
            remove_inline=reply_markup is None,
        )
        if attachments is not None:
            body["attachments"] = attachments
        await self._request("PUT", "/messages", params={"message_id": message_id}, json_data=body)

    async def delete_message(self, message_id: str, chat_id: Optional[int] = None):
        params = {"message_id": message_id}
        if chat_id is not None:
            params["chat_id"] = chat_id
        await self._request("DELETE", "/messages", params=params)

    async def answer_callback(self, callback_id: str, text: Optional[str] = None):
        body: Dict[str, Any] = {}
        if text:
            body["notification"] = text
        if not body:
            body["notification"] = ""
        await self._request("POST", "/answers", params={"callback_id": callback_id}, json_data=body)

    async def get_upload_url(self, upload_type: str) -> Dict[str, Any]:
        return await self._request("POST", "/uploads", params={"type": upload_type})

    async def upload_file(self, upload_url: str, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        data = aiohttp.FormData()
        data.add_field("data", file_bytes, filename=filename, content_type="application/octet-stream")
        session = await self._ensure_session()
        async with session.request(
            "POST",
            upload_url,
            data=data,
            proxy=self.proxy_url,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def send_photo(self, chat_id: Optional[int] = None, photo=None, caption: Optional[str] = None,
                         reply_markup=None, parse_mode: Optional[str] = None, user_id: Optional[int] = None):
        if isinstance(photo, types.BufferedInputFile):
            file_bytes = photo.data
            filename = photo.filename
        elif isinstance(photo, types.FSInputFile):
            file_bytes = photo.read()
            filename = photo.path.split("/")[-1]
        else:
            raise ValueError("Unsupported photo type")

        upload = await self.get_upload_url("image")
        upload_url = upload.get("url")
        if not upload_url:
            raise RuntimeError("Upload URL not returned by API")
        uploaded = await self.upload_file(upload_url, file_bytes, filename)
        attachment = {
            "type": "image",
            "payload": {
                "photos": uploaded.get("photos", {}),
            },
        }
        return await self.send_message(
            chat_id=chat_id,
            user_id=user_id,
            text=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            attachments=[attachment],
        )

    def _message_from_api(self, message_data: Optional[Dict[str, Any]]):
        if not message_data:
            return None
        body = message_data.get("body", {})
        sender = message_data.get("sender", {})
        recipient = message_data.get("recipient", {})
        user_id = sender.get("user_id") or sender.get("id") or 0
        username = sender.get("username")
        full_name = sender.get("name") or sender.get("full_name") or ""
        chat_id = recipient.get("chat_id") or recipient.get("user_id") or 0
        user = types.User(id=int(user_id), username=username, full_name=full_name)
        chat = types.Chat(id=int(chat_id))
        return types.Message(
            bot=self,
            message_id=str(body.get("mid")),
            chat=chat,
            from_user=user,
            text=body.get("text"),
            attachments=body.get("attachments") or [],
        )
