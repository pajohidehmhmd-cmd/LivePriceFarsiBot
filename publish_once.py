
import asyncio
import logging
import os
import html

import httpx
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.enums import ParseMode

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

API_URL = "https://nerkhara.com/api/v1/latest.json"

CHANNELS = {
    "mother": {
        "username": "@livepricefarsi",
        "title": "تابلو جامع قیمت فارسی",
        "items": ["usd", "gold-18k", "coin-emami", "btc", "eth"],
        "hashtags": "#USD #GOLD #COIN #BTC #ETH",
    },
    "dollar": {
        "username": "@dollarliveprice",
        "title": "قیمت دلار",
        "items": ["usd"],
        "hashtags": "#USD",
    },
    "gold": {
        "username": "@goldlivepricefarsi",
        "title": "قیمت طلا",
        "items": ["gold-18k", "gold-24k", "gold-mesghal"],
        "hashtags": "#GOLD",
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
        "hashtags": "#COIN",
    },
    "bitcoin": {
        "username": "@bitcoinlivefarsi",
        "title": "قیمت بیت‌کوین",
        "items": ["btc"],
        "hashtags": "#BTC",
    },
    "ethereum": {
        "username": "@ethereumlivefarsi",
        "title": "قیمت اتریوم",
        "items": ["eth"],
        "hashtags": "#ETH",
    },
}


def persian_digits(text):
    digits = "۰۱۲۳۴۵۶۷۸۹"
    return str(text).translate(
        str.maketrans("0123456789", digits)
    )


def format_number(value, decimals=0):
    return f"{float(value):,.{decimals}f}"


def format_item(item):

    item_id = item.get("id", "")

    name_data = item.get("name", {})

    if isinstance(name_data, dict):
        name = name_data.get("fa", item_id)
    else:
        name = str(name_data or item_id)

    price = item.get("price")

    if price is None:
        return ""

    if item.get("stale"):
        logging.warning("Skipping stale price: %s", item_id)
        return ""

    name = html.escape(str(name))

    lines = [f"<b>{name}</b>"]

    if item_id in ("btc", "eth"):

        price_irt = item.get("price_irt")

        if price_irt is not None:
            lines.append(
                f"ایران: <b>{format_number(price_irt)} تومان</b>"
            )

        lines.append(
            f"جهانی: <b>{format_number(price, 2)} تتر</b>"
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
            unit_text = html.escape(str(unit))

        lines.append(
            f"<b>{format_number(price)} {unit_text}</b>"
        )

    return "\n".join(lines)


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
        raise RuntimeError("Invalid API response")

    return {
        item["id"]: item
        for item in items
        if isinstance(item, dict) and item.get("id")
    }


def build_message(title, item_ids, prices, hashtags):

    sections = [
        f"<b>{html.escape(title)}</b>",
        "━━━━━━━━━━━━━━━━━━",
        "",
    ]

    found = 0

    for item_id in item_ids:

        item = prices.get(item_id)

        if not item:
            logging.warning("Price not found: %s", item_id)
            continue

        formatted = format_item(item)

        if formatted:
            sections.append(formatted)
            sections.append("")
            found += 1

    if found == 0:
        raise RuntimeError(
            f"No valid prices available for {title}"
        )

    sections.extend([
        "━━━━━━━━━━━━━━━━━━",
        hashtags,
    ])

    return persian_digits("\n".join(sections))


async def publish_all():

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    prices = await fetch_prices()

    bot = Bot(token=BOT_TOKEN)

    successful = 0
    failed = []

    try:

        for channel in CHANNELS.values():

            message = build_message(
                channel["title"],
                channel["items"],
                prices,
                channel["hashtags"],
            )

            try:

                await bot.send_message(
                    chat_id=channel["username"],
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )

                successful += 1

                logging.info(
                    "Published successfully: %s",
                    channel["username"],
                )

            except Exception:

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
