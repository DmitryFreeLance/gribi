from maxbot import types


def inline_menu(rows):
    """Builds reply keyboard (non-inline)."""
    keyboard_rows = []
    for row in rows:
        keyboard_row = []
        for label in row:
            text = label.text if hasattr(label, "text") else str(label)
            keyboard_row.append(types.KeyboardButton(text=text))
        keyboard_rows.append(keyboard_row)
    return types.ReplyKeyboardMarkup(keyboard=keyboard_rows, resize_keyboard=True)
