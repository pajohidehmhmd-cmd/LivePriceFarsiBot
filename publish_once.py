
import asyncio
import logging
import os

import httpx
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.enums import ParseMode

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
API_URL = "https://nerkhara.com/api/v1/latest.json"


# =================================
# CHANNELS
# =================================

CHANNELS = {
    "mother": {
        "username": "@livepricefarsi",
        "items": ["usd", "gold-18k", "coin-emami", "btc", "eth"],
        "hashtag": None,
    },

    "dollar": {
        "username": "@dollarliveprice",
        "items": ["usd"],
        "hashtag": "#USD",
    },

    "gold": {
        "username": "@goldlivepricefarsi",
        "items": ["gold-18k"],
        "hashtag": "#GOLD",
    },

    "coin": {
        "username": "@coinlivefarsi",
        "items": [
            "coin-emami",
            "coin-bahar-azadi",
            "coin-half",
            "coin-quarter",
            "coin-gram",
        ],
        "hashtag": "#COIN",
    },

    "bitcoin": {
        "username": "@bitcoinlivefarsi",
        "items": ["btc"],
        "hashtag": "#BTC",
    },

    "ethereum": {
        "username": "@ethereumlivefarsi",
        "items": ["eth"],
        "hashtag": "#ETH",
    },
}


# =================================
# MOTHER CHANNEL PERSIAN NAMES
# =================================

MOTHER_NAMES = {
    "usd": "دلار",
    "gold-18k": "هر گرم طلای 18 عیار",
    "coin-emami": "سکه امامی",
    "btc": "بیت‌کوین",
    "eth": "اتریوم",
}


# =================================
# PERSIAN COIN NAMES
# =================================

PERSIAN_COIN_NAMES = {
    "coin-emami": "سکه امامی",
    "coin-bahar-azadi": "سکه بهار آزادی",
    "coin-half": "نیم سکه",
    "coin-quarter": "ربع سکه",
    "coin-gram": "سکه گرمی",
}


# =================================
# NUMBER FORMATTING
# =================================

def format_number(value, decimals=0):

    number = float(str(value).replace(",", ""))

    return f"{number:,.{decimals}f}"


def get_currency(unit):

    unit = str(unit or "IRT").upper()

    if unit in ("IRT", "IRR", "TOMAN", "TOMANS", "IRI"):
        return "IRI"

    if unit in ("USD", "USDT"):
        return "USDT"

    return unit


# =================================
# FORMAT PRICE
# =================================

def format_item(item, channel_key):

    item_id = item.get("id", "")
    price = item.get("price")

    if price is None:
        return None

    if item.get("stale"):
        logging.warning("Stale price skipped: %s", item_id)
        return None

    # BITCOIN AND ETHEREUM

    if item_id in ("btc", "eth"):

        lines = []

        if channel_key == "mother":
            lines.append(
                f"<b>{MOTHER_NAMES[item_id]}</b>"
            )

        # First: USDT
        lines.append(
            f"<b>{format_number(price, 2)} USDT</b>"
        )

        # Second: IRI
        price_irt = item.get("price_irt")

        if price_irt is not None:
            lines.append(
                f"<b>{format_number(price_irt)} IRI</b>"
            )

        return "\n\n".join(lines)

    # GOLD CHANNEL

    if channel_key == "gold":

        return (
            "<b>هر گرم طلای 18 عیار</b>\n\n"
            f"<b>{format_number(price)} IRI</b>"
        )

    # COIN CHANNEL

    if channel_key == "coin":

        name = PERSIAN_COIN_NAMES.get(item_id)

        if not name:
            return None

        return (
            f"<b>{name}: "
            f"{format_number(price)} IRI</b>"
        )

    # MOTHER CHANNEL

    if channel_key == "mother":

        name = MOTHER_NAMES.get(item_id)

        if not name:
            return None

        currency = get_currency(item.get("unit"))

        return (
            f"<b>{name}</b>\n\n"
            f"<b>{format_number(price)} {currency}</b>"
        )

    # OTHER CHANNELS

    currency = get_currency(item.get("unit"))

    return (
        f"<b>{format_number(price)} {currency}</b>"
    )


# =================================
# FETCH PRICES
# =================================

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


# =================================
# BUILD MESSAGE
# =================================

def build_message(channel_key, prices):

    channel = CHANNELS[channel_key]

    sections = []

    for item_id in channel["items"]:

        item = prices.get(item_id)

        if not item:
            logging.warning(
                "Price not found: %s", item_id
            )
            continue

        formatted = format_item(item, channel_key)

        if formatted:
            sections.append(formatted)

    if not sections:
        raise RuntimeError(
            f"No valid prices for {channel_key}"
        )

    if channel["hashtag"]:
        sections.append(channel["hashtag"])

    message = "\n\n".join(sections)

    # Extra spacing in ALL six channels
    message = "\n" + message

    return message


# =================================
# PUBLISH TO TELEGRAM
# =================================

async def publish_all():

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    prices = await fetch_prices()

    bot = Bot(token=BOT_TOKEN)

    successful = 0
    failed = []

    try:

        for channel_key, channel in CHANNELS.items():

            try:

                message = build_message(
                    channel_key,
                    prices
                )

                await bot.send_message(
                    chat_id=channel["username"],
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )

                successful += 1

                logging.info(
                    "Published successfully: %s",
                    channel["username"]
                )

            except Exception:

                failed.append(channel["username"])

                logging.exception(
                    "Publishing failed: %s",
                    channel["username"]
                )

        print(
            f"Successful channels: {successful}/6"
        )

        if failed:
            raise RuntimeError(
                f"Failed channels: {failed}"
            )

    finally:
        await bot.session.close()


# =================================
# MAIN
# =================================

async def main():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    print("Live Price Farsi Bot started.")

    await publish_all()

    print("All six channels updated successfully.")


if __name__ == "__main__":
    asyncio.run(main())
