
import asyncio
import logging
import os

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.client.session.aiohttp import AiohttpSession

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
PROXY_URL = "http://127.0.0.1:12334"

ADMIN_USER_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_USER_IDS", "").split(",")
    if x.strip().isdigit()
}

try:
    PUBLISH_INTERVAL = max(
        1, int(os.getenv("PUBLISH_INTERVAL_MINUTES", "10"))
    )
except ValueError:
    PUBLISH_INTERVAL = 10

TIMEZONE = os.getenv("TIMEZONE", "Asia/Tehran")

CHANNELS = {
    "کانال مادر قیمت فارسی": "@livepricefarsi",
    "قیمت دلار": "@dollarliveprice",
    "قیمت طلا": "@goldlivepricefarsi",
    "قیمت ارز و سکه": "@coinlivefarsi",
    "قیمت بیت‌کوین": "@bitcoinlivefarsi",
    "قیمت اتریوم": "@ethereumlivefarsi",
}

if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    raise RuntimeError("BOT_TOKEN is missing in .env")

dp = Dispatcher()


def is_admin(user_id):
    return user_id in ADMIN_USER_IDS


def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 مدیریت کانال‌ها",
                    callback_data="admin:channels"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏱ فاصله انتشار",
                    callback_data="admin:interval"
                ),
                InlineKeyboardButton(
                    text="📊 وضعیت ربات",
                    callback_data="admin:status"
                )
            ]
        ]
    )


def channels_keyboard():
    rows = []

    for title, username in CHANNELS.items():
        rows.append([
            InlineKeyboardButton(
                text=title,
                url=f"https://t.me/{username.lstrip('@')}"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="⬅️ بازگشت",
            callback_data="admin:home"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ بازگشت به مدیریت",
                    callback_data="admin:home"
                )
            ]
        ]
    )


@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id

    if is_admin(user_id):
        await message.answer(
            "سلام مدیر! 👋\n\n"
            "دسترسی مدیریتی شما تأیید شده است.\n"
            "برای باز کردن پنل مدیریت دستور /admin را بفرستید."
        )
    else:
        await message.answer(
            "سلام! 👋\n"
            "به ربات قیمت فارسی خوش آمدید.\n\n"
            f"شناسه شما: {user_id}\n"
            "شما دسترسی مدیریتی ندارید."
        )


@dp.message(Command("myid"))
async def myid_handler(message: Message):
    await message.answer(
        f"شناسه عددی شما: {message.from_user.id}"
    )


@dp.message(Command("admin"))
async def admin_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ دسترسی غیرمجاز.")
        return

    await message.answer(
        "🛠 پنل مدیریت قیمت فارسی\n\n"
        "یکی از بخش‌های زیر را انتخاب کنید:",
        reply_markup=main_keyboard()
    )


@dp.callback_query(F.data.startswith("admin:"))
async def admin_callback(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ شما اجازه دسترسی ندارید.",
            show_alert=True
        )
        return

    action = callback.data

    if action == "admin:home":
        await callback.message.edit_text(
            "🛠 پنل مدیریت قیمت فارسی\n\n"
            "یکی از بخش‌های زیر را انتخاب کنید:",
            reply_markup=main_keyboard()
        )

    elif action == "admin:channels":
        channel_text = (
            "📢 مدیریت کانال‌ها\n\n"
            "تعداد کانال‌های ثبت‌شده: ۶\n\n"
            "برای باز کردن هر کانال روی نام آن کلیک کنید:"
        )

        await callback.message.edit_text(
            channel_text,
            reply_markup=channels_keyboard()
        )

    elif action == "admin:interval":
        await callback.message.edit_text(
            "⏱ تنظیمات انتشار\n\n"
            f"فاصله انتشار فعلی: {PUBLISH_INTERVAL} دقیقه\n"
            f"منطقه زمانی: {TIMEZONE}\n\n"
            "تغییر فاصله انتشار را در مرحله بعد فعال می‌کنیم.",
            reply_markup=back_keyboard()
        )

    elif action == "admin:status":
        await callback.message.edit_text(
            "📊 وضعیت ربات\n\n"
            "وضعیت پردازش: فعال\n"
            "اتصال تلگرام: برقرار\n"
            f"تعداد کانال‌های ثبت‌شده: {len(CHANNELS)}\n"
            f"فاصله انتشار: {PUBLISH_INTERVAL} دقیقه",
            reply_markup=back_keyboard()
        )

    await callback.answer()


async def main():
    logging.basicConfig(level=logging.INFO)

    if not ADMIN_USER_IDS:
        raise RuntimeError("ADMIN_USER_IDS is missing in .env")

    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=session)

    try:
        print("Live Price Farsi Bot is running...")
        await dp.start_polling(bot)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
