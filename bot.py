import os
import asyncio
from typing import Final
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, JobQueue
)

BOT_USERNAME: Final = "CryptoPriceBot"
BOT_TOKEN: Final = "Your Bot Token"
COINGECKO_API_URL: Final = "https://api.coingecko.com/api/v3"

MAIN_MENU, CHOOSING_CRYPTO, CHOOSING_CURRENCY, SETTING_ALERT = range(4)

SUPPORTED_CURRENCIES = ['usd', 'eur', 'gbp', 'jpy', 'aud', 'cad', 'inr']

user_favorites = {}
user_alerts = {}

def api_request(endpoint: str, params: dict = None):
    """Helper function to make API requests."""
    try:
        response = requests.get(f"{COINGECKO_API_URL}/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"API Error: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the bot and show the main menu."""
    await show_main_menu(update, context)
    return MAIN_MENU

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provide help information."""
    await update.message.reply_text(
        "💬 *Welcome to Crypto Price Bot!*\n"
        "You can:\n"
        "• View top cryptocurrencies\n"
        "• Check trending coins\n"
        "• Search and get details\n"
        "• Set alerts for price changes\n\n"
        "Commands:\n"
        "/start - Main menu\n"
        "/help - Display this help message\n"
        "/convert - Convert between crypto and fiat\n"
        "/favorites - Manage your favorite cryptocurrencies",
        parse_mode="Markdown"
    )

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu options."""
    keyboard = [
        [InlineKeyboardButton("Top Cryptocurrencies", callback_data="top100")],
        [InlineKeyboardButton("Trending Coins", callback_data="trending")],
        [InlineKeyboardButton("Search Cryptocurrency", callback_data="search")],
        [InlineKeyboardButton("Favorites", callback_data="favorites")],
        [InlineKeyboardButton("Quit", callback_data="quit")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🏦 *Crypto Price Bot*\nChoose an option below:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_crypto_details(update: Update, context: ContextTypes.DEFAULT_TYPE, crypto_id: str):
    """Fetch and display detailed cryptocurrency information."""
    currency = "usd"
    details = api_request("simple/price", {"ids": crypto_id, "vs_currencies": currency})
    if details:
        price = details[crypto_id][currency]
        await update.callback_query.edit_message_text(
            f"💰 *{crypto_id.capitalize()}*\n"
            f"Price: {price} {currency.upper()}",
            parse_mode="Markdown"
        )
    else:
        await update.callback_query.edit_message_text("❌ Failed to fetch crypto details.")

async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the user's favorite cryptocurrencies."""
    user_id = update.callback_query.from_user.id
    favorites = user_favorites.get(user_id, [])
    if not favorites:
        await update.callback_query.edit_message_text("You have no favorite cryptocurrencies.")
        return
    keyboard = [[InlineKeyboardButton(fav.capitalize(), callback_data=f"crypto:{fav}")] for fav in favorites]
    keyboard.append([InlineKeyboardButton("Back to Main Menu", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("⭐ Your Favorites:", reply_markup=reply_markup)

async def add_to_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE, crypto_id: str):
    """Add a cryptocurrency to the user's favorites."""
    user_id = update.callback_query.from_user.id
    user_favorites.setdefault(user_id, []).append(crypto_id)
    await update.callback_query.edit_message_text(f"Added {crypto_id.capitalize()} to favorites.")

async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set a price alert for a cryptocurrency."""
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /setalert <crypto> <above|below> <price>")
        return
    crypto = context.args[0]
    condition = context.args[1]
    threshold = float(context.args[2])
    user_id = update.message.from_user.id
    user_alerts[user_id] = (crypto, condition, threshold)
    await update.message.reply_text(f"Alert set for {crypto.capitalize()} {condition} ${threshold}.")

async def alert_check(context: ContextTypes.DEFAULT_TYPE):
    """Check alerts periodically."""
    for user_id, (crypto, condition, threshold) in list(user_alerts.items()):
        price = api_request("simple/price", {"ids": crypto, "vs_currencies": "usd"})
        if not price:
            continue
        current_price = price[crypto]["usd"]
        if (condition == "above" and current_price > threshold) or (condition == "below" and current_price < threshold):
            await context.bot.send_message(
                user_id, f"📈 Alert: {crypto.capitalize()} is now {condition} ${threshold}!"
            )
            del user_alerts[user_id]

def main():
    """Run the bot."""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setalert", set_alert))

    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="main_menu"))
    app.add_handler(CallbackQueryHandler(show_favorites, pattern="favorites"))
    app.run_polling()

if __name__ == "__main__":
    main()
