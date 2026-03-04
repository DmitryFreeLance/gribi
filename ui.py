from maxbot import types


def inline_menu(rows):
    """Builds inline menu where each button sends callback_data with menu: prefix."""
    inline_rows = []
    for row in rows:
        inline_row = []
        for label in row:
            text = label.text if hasattr(label, "text") else str(label)
            inline_row.append(
                types.InlineKeyboardButton(text=text, callback_data=f"menu:{text}")
            )
        inline_rows.append(inline_row)
    return types.InlineKeyboardMarkup(inline_keyboard=inline_rows)
