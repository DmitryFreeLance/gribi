from typing import Callable, Optional


class BaseFilter:
    def __call__(self, obj) -> bool:
        raise NotImplementedError


class CommandStart(BaseFilter):
    def __call__(self, message) -> bool:
        if not getattr(message, "text", None):
            return False
        text = message.text.strip()
        if not text.startswith("/"):
            return False
        cmd = text.split()[0][1:]
        if "@" in cmd:
            cmd = cmd.split("@", 1)[0]
        return cmd == "start"


class Command(BaseFilter):
    def __init__(self, commands):
        self.commands = set(commands or [])

    def __call__(self, message) -> bool:
        if not getattr(message, "text", None):
            return False
        text = message.text.strip()
        if not text.startswith("/"):
            return False
        cmd = text.split()[0][1:]
        if "@" in cmd:
            cmd = cmd.split("@", 1)[0]
        return cmd in self.commands


class _FieldFilter(BaseFilter):
    def __init__(self, field: str, predicate: Callable[[Optional[str]], bool]):
        self.field = field
        self.predicate = predicate

    def __call__(self, obj) -> bool:
        value = getattr(obj, self.field, None)
        return self.predicate(value)


class _FieldAccessor:
    def __init__(self, field: str):
        self.field = field

    def __eq__(self, other):
        return _FieldFilter(self.field, lambda v: v == other)

    def startswith(self, prefix: str):
        return _FieldFilter(self.field, lambda v: isinstance(v, str) and v.startswith(prefix))

    def __call__(self):
        return _FieldFilter(self.field, lambda v: v is not None)


class _F:
    @property
    def data(self):
        return _FieldAccessor("data")

    @property
    def text(self):
        return _FieldFilter("text", lambda v: v is not None)


F = _F()
