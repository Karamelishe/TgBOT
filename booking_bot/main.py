from __future__ import annotations

import asyncio
import logging
from typing import List, Tuple, Optional
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.utils.markdown import hbold
from aiogram.client.default import DefaultBotProperties

from config import load_settings
from db import Database, Slot
from keyboards import contact_request_kb, dates_kb, times_kb
from utils import local_to_utc_iso, utc_iso_to_local_str, unique_sorted_dates_local


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


settings = load_settings()

bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)
db = Database(settings.database_path)


async def ensure_user_record(message: Message) -> int:
    tg_user = message.from_user
    if tg_user is None:
        raise RuntimeError("No from_user")
    is_admin = 1 if tg_user.id in settings.admin_ids else 0
    user_id = await db.upsert_user(
        tg_user_id=tg_user.id,
        chat_id=message.chat.id,
        full_name=(tg_user.full_name or f"{tg_user.first_name or ''} {tg_user.last_name or ''}" ).strip(),
        is_admin=is_admin,
    )
    return user_id


async def list_dates_keyboard() -> Tuple[str, Optional[List[str]]]:
    free = await db.list_free_slots(since_utc_iso=datetime.now(timezone.utc).isoformat())
    if not free:
        return ("На ближайшее время свободных слотов нет. Попробуйте позже.", None)
    dates_local = unique_sorted_dates_local([s.slot_utc for s in free], settings.timezone)
    return ("Выберите дату:", dates_local)


async def list_times_keyboard(date_local: str) -> Tuple[str, Optional[List[Tuple[int, str]]]]:
    # Need to find free slots for that local date
    # To avoid DST issues, convert all free slots to local and filter by date string
    free = await db.list_free_slots(since_utc_iso=None)
    pairs: List[Tuple[int, str]] = []
    for s in free:
        d_str, t_str = utc_iso_to_local_str(s.slot_utc, settings.timezone)
        if d_str == date_local:
            pairs.append((s.id, t_str))
    pairs.sort(key=lambda x: x[1])
    if not pairs:
        return (f"На дату {date_local} свободных слотов нет.", None)
    return (f"Свободное время на {date_local}:", pairs)


@router.message(CommandStart())
async def on_start(message: Message):
    await db.init()
    await ensure_user_record(message)
    user = await db.get_user_by_tg(message.from_user.id)  # type: ignore[arg-type]
    if not user or not user.phone:
        await message.answer(
            "Здравствуйте! Для записи, пожалуйста, поделитесь номером телефона кнопкой ниже.",
            reply_markup=contact_request_kb(),
        )
        return

    text, dates = await list_dates_keyboard()
    if dates is None:
        await message.answer(text)
    else:
        await message.answer(text, reply_markup=dates_kb(dates))


@router.message(F.contact)
async def on_contact(message: Message):
    if not message.contact:
        return
    await ensure_user_record(message)
    await db.set_user_phone(message.from_user.id, message.contact.phone_number)  # type: ignore[arg-type]
    await message.answer("Спасибо! Теперь выберите дату и время для записи.")
    text, dates = await list_dates_keyboard()
    if dates is None:
        await message.answer(text)
    else:
        await message.answer(text, reply_markup=dates_kb(dates))


@router.callback_query(F.data == "refresh_dates")
async def on_refresh_dates(callback: CallbackQuery):
    text, dates = await list_dates_keyboard()
    if dates is None:
        await callback.message.edit_text(text)  # type: ignore[union-attr]
    else:
        await callback.message.edit_text(text, reply_markup=dates_kb(dates))  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data.startswith("choose_date:"))
async def on_choose_date(callback: CallbackQuery):
    date_local = callback.data.split(":", 1)[1]  # type: ignore[union-attr]
    text, pairs = await list_times_keyboard(date_local)
    if pairs is None:
        await callback.message.edit_text(text)  # type: ignore[union-attr]
    else:
        # label format HH:MM
        await callback.message.edit_text(text, reply_markup=times_kb(pairs))  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data == "back_to_dates")
async def on_back_to_dates(callback: CallbackQuery):
    text, dates = await list_dates_keyboard()
    if dates is None:
        await callback.message.edit_text(text)  # type: ignore[union-attr]
    else:
        await callback.message.edit_text(text, reply_markup=dates_kb(dates))  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def on_cancel(callback: CallbackQuery):
    await callback.message.edit_text("Отменено.")  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data.startswith("book:"))
async def on_book(callback: CallbackQuery):
    slot_id = int(callback.data.split(":", 1)[1])  # type: ignore[union-attr]
    tg_user = callback.from_user
    user = await db.get_user_by_tg(tg_user.id)
    if not user or not user.phone:
        await callback.answer("Сначала поделитесь номером телефона через /start", show_alert=True)
        return
    try:
        booking_id = await db.create_booking(user.id, slot_id)
    except Exception as e:  # typically UNIQUE constraint
        logger.exception("Booking failed: %s", e)
        await callback.answer("Увы, этот слот только что заняли. Выберите другой.", show_alert=True)
        # refresh times list
        # find date of slot to refresh list
        slots = await db.list_slots()
        target: Optional[Slot] = next((s for s in slots if s.id == slot_id), None)
        if target:
            date_local, _ = utc_iso_to_local_str(target.slot_utc, settings.timezone)
            text, pairs = await list_times_keyboard(date_local)
            if pairs is None:
                await callback.message.edit_text(text)  # type: ignore[union-attr]
            else:
                await callback.message.edit_text(text, reply_markup=times_kb(pairs))  # type: ignore[union-attr]
        return

    # success
    # load slot for confirmation
    slots = await db.list_slots()
    target: Optional[Slot] = next((s for s in slots if s.id == slot_id), None)
    if not target:
        await callback.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)
        return
    date_local, time_local = utc_iso_to_local_str(target.slot_utc, settings.timezone)
    await callback.message.edit_text(
        f"✅ Запись подтверждена на {hbold(date_local)} в {hbold(time_local)}.\n"
        f"Мы пришлём напоминание за 2 часа до посещения."
    )  # type: ignore[union-attr]
    await callback.answer()

    # notify admins
    note = target.note or ""
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=(
                    f"Новое бронирование\n"
                    f"Клиент: {hbold(user.full_name)} ({user.phone})\n"
                    f"Дата: {hbold(date_local)} {hbold(time_local)}\n"
                    f"Слот ID: {target.id}\n"
                    f"Примечание: {note}"
                ),
            )
        except Exception:
            pass


# Admin commands

def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command(commands=["addslot"]))
async def cmd_addslot(message: Message):
    if not _is_admin(message.from_user.id):  # type: ignore[arg-type]
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("Использование: /addslot YYYY-MM-DD HH:MM [длительность_мин] [примечание]")
        return
    date_str, time_str = parts[1], parts[2]
    duration = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 60
    note = " ".join(parts[4:]) if len(parts) >= 5 else None
    local_dt = f"{date_str} {time_str}"
    utc_iso = local_to_utc_iso(local_dt, settings.timezone)
    slot_id = await db.add_slot(utc_iso, duration_minutes=duration, note=note, created_by=message.from_user.id)  # type: ignore[arg-type]
    d_loc, t_loc = utc_iso_to_local_str(utc_iso, settings.timezone)
    await message.reply(f"Слот добавлен: {d_loc} {t_loc} (ID {slot_id})")


@router.message(Command(commands=["addslots"]))
async def cmd_addslots(message: Message):
    if not _is_admin(message.from_user.id):  # type: ignore[arg-type]
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("Использование: /addslots YYYY-MM-DD HH:MM [HH:MM ...] [длительность_мин]")
        return
    date_str = parts[1]
    times: List[str] = []
    duration = 60
    # Parse times until non-time token
    for token in parts[2:]:
        if ":" in token and len(token) <= 5:
            times.append(token)
        elif token.isdigit():
            duration = int(token)
        else:
            # ignore
            pass
    if not times:
        await message.reply("Укажите хотя бы одно время HH:MM")
        return
    created: List[int] = []
    for t in times:
        utc_iso = local_to_utc_iso(f"{date_str} {t}", settings.timezone)
        slot_id = await db.add_slot(utc_iso, duration_minutes=duration, created_by=message.from_user.id)  # type: ignore[arg-type]
        created.append(slot_id)
    await message.reply(f"Добавлено слотов: {len(created)} на {date_str}")


@router.message(Command(commands=["listfree"]))
async def cmd_listfree(message: Message):
    if not _is_admin(message.from_user.id):  # type: ignore[arg-type]
        return
    parts = message.text.split()
    date_only = parts[1] if len(parts) >= 2 else None
    free = await db.list_free_slots(since_utc_iso=datetime.now(timezone.utc).isoformat(), date_only=None)
    if date_only:
        # filter by local date
        filtered = []
        for s in free:
            d_loc, t_loc = utc_iso_to_local_str(s.slot_utc, settings.timezone)
            if d_loc == date_only:
                filtered.append((s.id, d_loc, t_loc))
        free_pairs = filtered
    else:
        free_pairs = [(s.id, *utc_iso_to_local_str(s.slot_utc, settings.timezone)) for s in free]
    if not free_pairs:
        await message.reply("Свободных слотов нет")
        return
    lines = [f"ID {sid}: {d} {t}" for sid, d, t in free_pairs]
    await message.reply("Свободные слоты:\n" + "\n".join(lines))


@router.message(Command(commands=["listbookings"]))
async def cmd_listbookings(message: Message):
    if not _is_admin(message.from_user.id):  # type: ignore[arg-type]
        return
    parts = message.text.split()
    date_only = parts[1] if len(parts) >= 2 else None
    rows = await db.list_bookings()
    if date_only:
        rows = [r for r in rows if utc_iso_to_local_str(r[2].slot_utc, settings.timezone)[0] == date_only]
    if not rows:
        await message.reply("Бронирований нет")
        return
    lines = []
    for b, u, s in rows:
        d, t = utc_iso_to_local_str(s.slot_utc, settings.timezone)
        lines.append(f"{d} {t} — {u.full_name} ({u.phone}), booking #{b.id}, slot {s.id}")
    await message.reply("Бронирования:\n" + "\n".join(lines))


@router.message(Command(commands=["delslot"]))
async def cmd_delslot(message: Message):
    if not _is_admin(message.from_user.id):  # type: ignore[arg-type]
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("Использование: /delslot SLOT_ID")
        return
    slot_id = int(parts[1])
    deleted = await db.delete_slot(slot_id)
    if deleted:
        await message.reply(f"Слот {slot_id} удалён")
    else:
        await message.reply("Слот не найден или уже удалён")


async def reminder_worker() -> None:
    await db.init()
    while True:
        now_utc = datetime.now(timezone.utc)
        try:
            candidates = await db.find_bookings_for_reminder(now_utc)
            if candidates:
                for booking_id, chat_id, slot_id, slot_iso in candidates:
                    d, t = utc_iso_to_local_str(slot_iso, settings.timezone)
                    try:
                        await bot.send_message(chat_id, f"Напоминание: вы записаны на {d} в {t} (через 2 часа)")
                        await db.mark_reminder_sent(booking_id)
                    except Exception as e:
                        logger.exception("Failed to send reminder: %s", e)
        except Exception as e:
            logger.exception("Reminder worker error: %s", e)
        await asyncio.sleep(60)


async def main() -> None:
    await db.init()
    asyncio.create_task(reminder_worker())
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass