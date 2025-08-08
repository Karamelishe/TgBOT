from __future__ import annotations

from typing import List, Tuple, Optional
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def contact_request_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отправить номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажмите кнопку, чтобы поделиться номером",
    )
    return kb


def dates_kb(dates_iso: List[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for date_iso in dates_iso:
        # date_iso format YYYY-MM-DD
        builder.button(text=date_iso, callback_data=f"choose_date:{date_iso}")
    builder.adjust(2)
    builder.button(text="Обновить", callback_data="refresh_dates")
    builder.button(text="Отмена", callback_data="cancel")
    return builder.as_markup()


def times_kb(pairs: List[Tuple[int, str, Optional[str]]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot_id, label, note in pairs:
        # Add note to button text if available
        button_text = label
        if note:
            button_text += f" ({note})"
        builder.button(text=button_text, callback_data=f"select_time:{slot_id}")
    builder.adjust(2)
    builder.button(text="Назад", callback_data="back_to_dates")
    builder.button(text="Отмена", callback_data="cancel")
    return builder.as_markup()


def guests_count_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 9):  # 1-8 guests
        builder.button(text=str(i), callback_data=f"guests:{i}")
    builder.adjust(4)
    builder.button(text="Отмена", callback_data="cancel")
    return builder.as_markup()


def reminder_settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="За 1 час", callback_data="reminder:1")
    builder.button(text="За 2 часа", callback_data="reminder:2")
    builder.button(text="За 3 часа", callback_data="reminder:3")
    builder.button(text="За 6 часов", callback_data="reminder:6")
    builder.button(text="За 12 часов", callback_data="reminder:12")
    builder.button(text="За 24 часа", callback_data="reminder:24")
    builder.button(text="Без напоминания", callback_data="reminder:0")
    builder.adjust(2)
    builder.button(text="Отмена", callback_data="cancel")
    return builder.as_markup()


def confirm_booking_kb(slot_id: int, guests_count: int, reminder_hours: Optional[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"confirm_booking:{slot_id}:{guests_count}:{reminder_hours or 0}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    return builder.as_markup()