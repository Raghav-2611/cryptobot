import os
import asyncio
from typing import Final
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters, JobQueue
)

# Constants
BOT_USERNAME: Final = 'xyz'
BOT_TOKEN: Final = "Your Bot Token"
COINGECKO_API_URL: Final = "https://api.coingecko.com/api/v3"

# Conversation states
MAIN_MENU, CHOOSING_CRYPTO, CHOOSING_CURRENCY, TYPING_SEARCH, COMPARE_SELECTION = range(5)

# Supported currencies
SUPPORTED_CURRENCIES = ['usd', 'eur', 'gbp', 'jpy', 'aud', 'cad', 'chf', 'cny', 'inr']

# Store user alerts
user_alerts = {}

# API HELPER FUNCTIONS

def get_top_cryptos(limit=100):
    """Fetch top cryptocurrencies by market cap."""
    try:
        response = requests.get(f"{COINGECKO_API_URL}/coins/markets", params={
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': limit,
            'page': 1,
            'sparkline': False
        })
        response.raise_for_status()  # Raise an HTTPError if the response is unsuccessful
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching top cryptos: {e}")
    return []

def get_trending_cryptos():
    """Fetch trending cryptocurrencies."""
    try:
        response = requests.get(f"{COINGECKO_API_URL}/search/trending")
        response.raise_for_status()
        return response.json().get('coins', [])
    except requests.RequestException as e:
        print(f"Error fetching trending cryptos: {e}")
    return []

def get_crypto_details(crypto_id: str, currency: str = 'usd'):
    """Fetch details for a specific cryptocurrency."""
    try:
        params = {'ids': crypto_id, 'vs_currencies': currency, 'include_24hr_change': 'true', 'include_market_cap': 'true'}
        response = requests.get(f"{COINGECKO_API_URL}/simple/price", params=params)
        response.raise_for_status()
        return response.json().get(crypto_id)
    except requests.RequestException as e:
        print(f"Error fetching crypto details: {e}")
    return None

# COMMAND HANDLER FUNCTIONS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the bot and show the main menu."""
    await show_main_menu(update, context)
    return MAIN_MENU

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display help information."""
    help_text = (
        "Welcome to the Crypto Price Bot!\n\n"
        "Commands:\n"
        "/start - Show main menu\n"
        "/help - Show this help message\n"
        "/convert - Convert cryptocurrencies\n"
        "/setalert - Set a price alert\n\n"
        "You can check prices, view trending coins, search for a specific cryptocurrency, or set alerts."
    )
    await update.message.reply_text(help_text)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, is_comparing: bool = False) -> None:
    """Display the main menu options."""
    keyboard = [
        [InlineKeyboardButton("Top 100 Cryptocurrencies", callback_data='top100')],
        [InlineKeyboardButton("Trending Cryptocurrencies", callback_data='trending')],
        [InlineKeyboardButton("Search Cryptocurrency", callback_data='search')],
        [InlineKeyboardButton("Quit", callback_data='quit')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "Select an option below:" if is_comparing else "Welcome to the Crypto Price Bot! What would you like to do?"
    await update.message.reply_text(text, reply_markup=reply_markup)

async def show_crypto_list(update: Update, context: ContextTypes.DEFAULT_TYPE, cryptos, title) -> None:
    """Display a list of cryptocurrencies with inline buttons."""
    keyboard = []
    for i in range(0, len(cryptos), 2):
        row = [
            InlineKeyboardButton(f"{crypto['name']} ({crypto['symbol'].upper()})", callback_data=f"crypto:{crypto['id']}")
            for crypto in cryptos[i:i + 2]
        ]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(title, reply_markup=reply_markup)

async def show_crypto_details(update: Update, context: ContextTypes.DEFAULT_TYPE, crypto_id: str, currency: str) -> None:
    """Fetch and display details for a specific cryptocurrency."""
    await asyncio.sleep(1)  # Avoid API rate limits
    details = get_crypto_details(crypto_id, currency)
    if details:
        price = details.get(currency, 'N/A')
        change_24h = details.get(f'{currency}_24h_change', 'N/A')
        message = (
            f"💰 {crypto_id.capitalize()} ({currency.upper()})\n"
            f"Price: {price} {currency.upper()}\n"
            f"24h Change: {change_24h}%\n"
        )
        await update.callback_query.edit_message_text(message)
    else:
        await update.callback_query.edit_message_text("Unable to retrieve cryptocurrency details.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user messages and search for cryptocurrencies."""
    user_input = update.message.text.lower()
    search_results = requests.get(f"{COINGECKO_API_URL}/search", params={'query': user_input}).json()
    coins = search_results.get('coins', [])
    if coins:
        await show_crypto_list(update, context, coins[:10], "Search Results:")
        return CHOOSING_CRYPTO
    else:
        await update.message.reply_text("No results found.")
        await show_main_menu(update, context)
        return MAIN_MENU

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    print(f"Error: {context.error}")

def get_crypto_price(crypto: str, currency: str = 'usd'):
    """Retrieve the price of a specific cryptocurrency."""
    params = {'ids': crypto, 'vs_currencies': currency}
    response = requests.get(COINGECKO_API_URL + '/simple/price', params=params)
    data = response.json()
    return data.get(crypto, {}).get(currency, 'Price not available')

async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Convert a specified cryptocurrency amount to a target currency."""
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /convert <crypto> <currency> <amount>")
        return
    crypto = context.args[0].lower()
    currency = context.args[1].lower()
    amount = float(context.args[2])
    price = get_crypto_price(crypto, currency)
    if price != 'Price not available':
        converted_amount = price * amount
        await update.message.reply_text(f"{amount} {crypto.capitalize()} is worth {converted_amount} {currency.upper()}.")
    else:
        await update.message.reply_text('Price not available.')

def set_price_alert(user_id, crypto, threshold_price, condition):
    """Set a price alert for a user."""
    user_alerts[user_id] = (crypto, threshold_price, condition)

async def set_alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle setting price alerts."""
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /setalert <crypto> <above|below> <price>")
        return
    crypto = context.args[0].lower()
    condition = context.args[1].lower()
    price = float(context.args[2])
    if condition not in ['above', 'below']:
        await update.message.reply_text("Specify 'above' or 'below'.")
        return
    user_id = update.message.from_user.id
    set_price_alert(user_id, crypto, price, condition)
    await update.message.reply_text(f"Alert set for {crypto.capitalize()} {condition} ${price}.")

async def alert_check(context: ContextTypes.DEFAULT_TYPE):
    """Periodic check for price alerts."""
    for user_id, (crypto, threshold_price, condition) in list(user_alerts.items()):
        price = get_crypto_price(crypto)
        if (condition == 'above' and price > threshold_price) or (condition == 'below' and price < threshold_price):
            await context.bot.send_message(user_id, f"Alert: {crypto.capitalize()} is now {condition} ${threshold_price}.")
            del user_alerts[user_id]  # Remove alert after notifying user

def main() -> None:
    """Main function to run the bot."""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("convert", convert_command))
    app.add_handler(CommandHandler("setalert", set_alert_command))

    # Initialize and run the alert checking job every 5 minutes
    app.job_queue.run_repeating(alert_check, interval=300, first=10)

    app.add_handler(CallbackQueryHandler(show_main_menu, pattern='main_menu'))
    app.add_handler(CallbackQueryHandler(lambda u, c: show_crypto_list(u, c, get_top_cryptos(10), "Top Cryptocurrencies"), pattern='top100'))
    app.add_handler(CallbackQueryHandler(lambda u, c: show_crypto_list(u, c, get_trending_cryptos(), "Trending Cryptocurrencies"), pattern='trending'))
    app.add_handler(CallbackQueryHandler(lambda u, c: show_crypto_details(u, c, u.callback_query.data.split(":")[1], 'usd'), pattern='^crypto:'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == '__main__':
    main()
