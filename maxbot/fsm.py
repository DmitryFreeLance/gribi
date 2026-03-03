import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, Optional


class State:
    def __init__(self, name: Optional[str] = None):
        self.name = name

    def __str__(self) -> str:
        return self.name or ""


class StatesGroupMeta(type):
    def __new__(mcls, name, bases, attrs):
        cls = super().__new__(mcls, name, bases, attrs)
        for attr_name, value in attrs.items():
            if isinstance(value, State):
                value.name = f"{name}:{attr_name}"
        return cls


class StatesGroup(metaclass=StatesGroupMeta):
    pass


@dataclass(frozen=True)
class StorageKey:
    chat_id: int
    user_id: int
    bot_id: Optional[int] = None


class SQLiteStorage:
    def __init__(self, path: str):
        self.path = path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fsm_state (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    state TEXT,
                    data TEXT,
                    PRIMARY KEY (chat_id, user_id)
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _get_row(self, chat_id: int, user_id: int) -> Optional[tuple]:
        conn = sqlite3.connect(self.path)
        try:
            cur = conn.execute(
                "SELECT state, data FROM fsm_state WHERE chat_id=? AND user_id=?",
                (chat_id, user_id),
            )
            return cur.fetchone()
        finally:
            conn.close()

    def get_state(self, chat_id: int, user_id: int) -> Optional[str]:
        row = self._get_row(chat_id, user_id)
        return row[0] if row else None

    def set_state(self, chat_id: int, user_id: int, state: Optional[str]) -> None:
        conn = sqlite3.connect(self.path)
        try:
            conn.execute(
                "INSERT INTO fsm_state(chat_id, user_id, state, data) VALUES(?,?,?,?) "
                "ON CONFLICT(chat_id, user_id) DO UPDATE SET state=excluded.state",
                (chat_id, user_id, state, None),
            )
            conn.commit()
        finally:
            conn.close()

    def get_data(self, chat_id: int, user_id: int) -> Dict[str, Any]:
        row = self._get_row(chat_id, user_id)
        if not row or not row[1]:
            return {}
        try:
            return json.loads(row[1])
        except json.JSONDecodeError:
            return {}

    def set_data(self, chat_id: int, user_id: int, data: Dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        conn = sqlite3.connect(self.path)
        try:
            conn.execute(
                "INSERT INTO fsm_state(chat_id, user_id, state, data) VALUES(?,?,?,?) "
                "ON CONFLICT(chat_id, user_id) DO UPDATE SET data=excluded.data",
                (chat_id, user_id, None, payload),
            )
            conn.commit()
        finally:
            conn.close()

    def update_data(self, chat_id: int, user_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        data = self.get_data(chat_id, user_id)
        data.update(updates)
        payload = json.dumps(data, ensure_ascii=False)
        conn = sqlite3.connect(self.path)
        try:
            conn.execute(
                "INSERT INTO fsm_state(chat_id, user_id, state, data) VALUES(?,?,?,?) "
                "ON CONFLICT(chat_id, user_id) DO UPDATE SET data=excluded.data",
                (chat_id, user_id, None, payload),
            )
            conn.commit()
        finally:
            conn.close()
        return data

    def clear(self, chat_id: int, user_id: int) -> None:
        conn = sqlite3.connect(self.path)
        try:
            conn.execute(
                "INSERT INTO fsm_state(chat_id, user_id, state, data) VALUES(?,?,?,?) "
                "ON CONFLICT(chat_id, user_id) DO UPDATE SET state=NULL, data=NULL",
                (chat_id, user_id, None, None),
            )
            conn.commit()
        finally:
            conn.close()


class FSMContext:
    def __init__(self, storage: SQLiteStorage, key: StorageKey):
        self.storage = storage
        self.key = key

    async def get_state(self) -> Optional[str]:
        return self.storage.get_state(self.key.chat_id, self.key.user_id)

    async def set_state(self, state: Optional[State]) -> None:
        state_name = state.name if isinstance(state, State) else state
        self.storage.set_state(self.key.chat_id, self.key.user_id, state_name)

    async def get_data(self) -> Dict[str, Any]:
        return self.storage.get_data(self.key.chat_id, self.key.user_id)

    async def update_data(self, **kwargs: Any) -> Dict[str, Any]:
        return self.storage.update_data(self.key.chat_id, self.key.user_id, kwargs)

    async def clear(self) -> None:
        self.storage.clear(self.key.chat_id, self.key.user_id)
