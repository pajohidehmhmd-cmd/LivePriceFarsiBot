
import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

import httpx
from dotenv import load_dotenv
from aiogram import Bot

load_dotenv()

# ==============================
# SETTINGS
# ==============================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

API_URL = "https://nerkhara.com/api/v1/latest.json"

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

CHANNELS = {
    "mother": {
        "username": "@livepricefarsi",
        "title": "تابلو جامع قیمت فارسی",
        "items": [
            "usd",
            "gold-18k",
            "coin-emami",
            "btc",
            "eth",
        ],
    },
    "dollar": {
        "username": "@dollarliveprice",
        "title": "قیمت دلار",
        "items": ["usd"],
    },
    "gold": {
        "username": "@goldlivepricefarsi",
        "title": "قیمت طلا",
        "items": ["gold-18k", "gold-24k", "gold-mesghal"],
    },
    "coin": {
        "username": "@coinlivefarsi",
        "title": "قیمت ارز و سکه",
        "items": [
            "coin-emami",
            "coin-bahar-azadi",
            "coin-half",
            "coin-quarter",
            "coin-gram",
        ],
    },
    "bitcoin": {
        "username": "@bitcoinlivefarsi",
        "title": "قیمت بیت کوین",
        "items": ["btc"],
    },
    "ethereum": {
        "username": "@ethereumlivefarsi",
        "title": "قیمت اتریوم",
        "items": ["eth"],
    },
}


# ==============================
# HELPERS
# ==============================

def persian_digits(text):
    digits = "۰۱۲۳۴۵۶۷۸۹"
    return str(text).translate(
        str.maketrans("0123456789", digits)
    )


def format_number(value, decimals=0):
    return f"{float(value):,.{decimals}f}"


def get_update_time(item, fallback=None):
    value = item.get("updated_utc") or fallback

    if not value:
        return "نامشخص"

    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(TEHRAN_TZ).strftime("%H:%M")
    except (ValueError, TypeError):
        return "نامشخص"


def format_item(item, fallback_time=None):
    item_id = item.get("id", "")

    name_data = item.get("name", {})
    if isinstance(name_data, dict):
        name = name_data.get("fa", item_id)
    else:
        name = str(name_data or item_id)

    price = item.get("price")

    if price is None:
        return []

    lines = []

    # Cryptocurrency prices
    if item_id in ("btc", "eth"):

        price_irt = item.get("price_irt")

        if price_irt is not None:
            lines.append(
                f"💰 قیمت بازار ایران: "
                f"{format_number(price_irt)} تومان"
            )

        lines.append(
            f"🌍 قیمت جهانی: "
            f"{format_number(price, 2)} تتر"
        )

    else:
        unit = item.get("unit", "IRT")

        if unit == "IRT":
            unit_text = "تومان"
        elif unit == "USD":
            unit_text = "دلار"
        elif unit == "USDT":
            unit_text = "تتر"
        else:
            unit_text = unit

        lines.append(
            f"💰 قیمت: {format_number(price)} {unit_text}"
        )

    change = item.get("change_pct")

    if change is not None:
        sign = "+" if float(change) > 0 else ""
        lines.append(
            f"📈 تغییر ۲۴ ساعته: {sign}{change}%"
        )

    update_time = get_update_time(item, fallback_time)

    lines.append(f"🕒 آخرین به‌روزرسانی: {update_time}")

    if item.get("stale"):
        lines.append("⚠️ هشدار: اطلاعات این نرخ قدیمی است.")

    return [
        f"🔹 {name}",
        *lines,
    ]


# ==============================
# FETCH PRICES
# ==============================

async def fetch_prices():

    async with httpx.AsyncClient(
        timeout=30,
        headers={
            "User-Agent": "LivePriceFarsiBot/1.0"
        }
    ) as client:

        response = await client.get(API_URL)
        response.raise_for_status()

        data = response.json()

    items = data.get("items")

    if not isinstance(items, list) or not items:
        raise RuntimeError(
            "Invalid response from NerkhAra API"
        )

    return {
        item["id"]: item
        for item in items
        if isinstance(item, dict) and item.get("id")
    }, data.get("generated_utc")


# ==============================
# BUILD MESSAGES
# ==============================

def build_message(title, item_ids, prices, generated_time):

    sections = [
        f"📊 {title}",
        "━━━━━━━━━━━━━━━━━━",
        "",
    ]

    found = 0

    for item_id in item_ids:

        item = prices.get(item_id)

        if not item:
            logging.warning(
                "Price not found: %s", item_id
            )
            continue

        formatted = format_item(item, generated_time)

        if formatted:
            sections.extend(formatted)
            sections.extend(["", "━━━━━━━━━━━━━━━━━━", ""])
            found += 1

    if found == 0:
        raise RuntimeError(
            f"No valid prices available for {title}"
        )

    sections.extend([
        "📌 واحد قیمت‌ها مطابق واحد درج‌شده است.",
        "📡 منبع اطلاعات: NerkhAra",
        "🔗 https://nerkhara.com",
        "",
        "⚠️ قیمت‌ها صرفاً جهت اطلاع‌رسانی هستند.",
    ])

    return persian_digits("\n".join(sections))


# ==============================
# PUBLISH TO TELEGRAM
# ==============================

async def publish_all():

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    prices, generated_time = await fetch_prices()

    bot = Bot(token=BOT_TOKEN)

    successful = 0
    failed = []

    try:

        for key, channel in CHANNELS.items():

            message = build_message(
                channel["title"],
                channel["items"],
                prices,
                generated_time,
            )

            try:

                await bot.send_message(
                    chat_id=channel["username"],
                    text=message,
                    disable_web_page_preview=True,
                )

                successful += 1

                logging.info(
                    "Published successfully: %s",
                    channel["username"],
                )

            except Exception as error:

                failed.append(channel["username"])

                logging.exception(
                    "Publishing failed: %s",
                    channel["username"],
                )

        print(f"Successful channels: {successful}/6")

        if failed:
            raise RuntimeError(
                f"Failed channels: {failed}"
            )

    finally:
        await bot.session.close()


# ==============================
# MAIN
# ==============================

async def main():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    print("Live Price Farsi Bot started.")

    await publish_all()

    print("All six channels updated successfully.")


if __name__ == "__main__":
    asyncio.run(main())
