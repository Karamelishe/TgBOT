from __future__ import annotations

from typing import List, Tuple
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


def times_kb(pairs: List[Tuple[int, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot_id, label in pairs:
        builder.button(text=label, callback_data=f"book:{slot_id}")
    builder.adjust(3)
    builder.button(text="Назад", callback_data="back_to_dates")
    builder.button(text="Отмена", callback_data="cancel")
    return builder.as_markup()