import os
import requests
from typing import Final
from cachetools import TTLCache
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

BOT_USERNAME: Final = "CryptoPriceBot"
BOT_TOKEN: Final = "Your Bot Token"
COINGECKO_API_URL: Final = "https://api.coingecko.com/api/v3"
CACHE_TTL = 300

cache = TTLCache(maxsize=100, ttl=CACHE_TTL)
user_favorites = {}

def api_request(endpoint: str, params: dict = None):
    """Fetch data from API with caching."""
    cache_key = f"{endpoint}:{params}"
    if cache_key in cache:
        return cache[cache_key]
    try:
        response = requests.get(f"{COINGECKO_API_URL}/{endpoint}", params=params)
        response.raise_for_status()
        data = response.json()
        cache[cache_key] = data
        return data
    except requests.RequestException as e:
        print(f"API Error: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update)
    
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Welcome to Crypto Price Bot!*\n"
        "Commands:\n"
        "/start - Main menu\n"
        "/help - Help message\n"
        "/favorites - Show favorite cryptos",
        parse_mode="Markdown"
    )

async def show_main_menu(update: Update):
    keyboard = [
        [InlineKeyboardButton("Top Cryptocurrencies", callback_data="top100")],
        [InlineKeyboardButton("Favorites", callback_data="favorites")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "*Crypto Price Bot*\nChoose an option:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def show_top_cryptos(update: Update):
    top_cryptos = api_request("coins/markets", {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 10})
    if not top_cryptos:
        await update.callback_query.edit_message_text("❌ Failed to fetch top cryptocurrencies.")
        return
    keyboard = [[InlineKeyboardButton(f"{crypto['name']} ({crypto['symbol'].upper()})", callback_data=f"crypto:{crypto['id']}")] for crypto in top_cryptos]
    await update.callback_query.edit_message_text(
        "*Top Cryptocurrencies:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def show_favorites(update: Update):
    user_id = update.callback_query.from_user.id
    favorites = user_favorites.get(user_id, [])
    if not favorites:
        await update.callback_query.edit_message_text("No favorite cryptocurrencies yet.")
        return
    keyboard = [[InlineKeyboardButton(fav.capitalize(), callback_data=f"crypto:{fav}")] for fav in favorites]
    await update.callback_query.edit_message_text(
        "Your Favorites:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="main_menu"))
    app.add_handler(CallbackQueryHandler(show_top_cryptos, pattern="top100"))
    app.add_handler(CallbackQueryHandler(show_favorites, pattern="favorites"))

    app.run_polling()

if __name__ == "__main__":
    main()
