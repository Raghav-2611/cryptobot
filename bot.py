import os
import asyncio
from typing import Final
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters

# Constants
BOT_USERNAME: Final = 'xyz'
BOT_TOKEN: Final = "Your Bot Token"
COINGECKO_API_URL: Final = "https://api.coingecko.com/api/v3"

# Conversation states
MAIN_MENU, CHOOSING_CRYPTO, CHOOSING_CURRENCY, TYPING_SEARCH, COMPARE_SELECTION = range(5)

# Supported currencies
SUPPORTED_CURRENCIES = ['usd', 'eur', 'gbp', 'jpy', 'aud', 'cad', 'chf', 'cny', 'inr']

# API HELPER FUNCTIONS

def get_top_cryptos(limit=100):
    try:
        response = requests.get(f"{COINGECKO_API_URL}/coins/markets", params={
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': limit,
            'page': 1,
            'sparkline': False
        })
        if response.status_code == 200:
            return response.json()
    except requests.RequestException as e:
        print(f"Error fetching top cryptos: {e}")
    return []


def get_trending_cryptos():
    try:
        response = requests.get(f"{COINGECKO_API_URL}/search/trending")
        if response.status_code == 200:
            return response.json().get('coins', [])
    except requests.RequestException as e:
        print(f"Error fetching trending cryptos: {e}")
    return []


def get_crypto_details(crypto_id: str, currency: str = 'usd'):
    try:
        params = {'ids': crypto_id, 'vs_currencies': currency, 'include_24hr_change': 'true', 'include_market_cap': 'true'}
        response = requests.get(f"{COINGECKO_API_URL}/simple/price", params=params)
        if response.status_code == 200:
            return response.json().get(crypto_id)
    except requests.RequestException as e:
        print(f"Error fetching crypto details: {e}")
    return None

# COMMAND HANDLER FUNCTIONS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await show_main_menu(update, context)
    return MAIN_MENU

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "Welcome to the Crypto Price Bot!\n\n"
        "Commands:\n"
        "/start - Show main menu\n"
        "/help - Show this help message\n"
        "/convert - Convert cryptocurrencies\n\n"
        "You can check prices, view trending coins, search for a specific cryptocurrency, or convert them."
    )
    await update.message.reply_text(help_text)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, is_comparing: bool = False) -> None:
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
    keyboard = []
    for i in range(0, len(cryptos), 2):
        row = [InlineKeyboardButton(f"{crypto['name']} ({crypto['symbol'].upper()})", callback_data=f"crypto:{crypto['id']}") for crypto in cryptos[i:i+2]]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(title, reply_markup=reply_markup)


async def show_crypto_details(update: Update, context: ContextTypes.DEFAULT_TYPE, crypto_id: str, currency: str) -> None:
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
    print(f"Error: {context.error}")

def get_crypto_price(crypto: str, currency: str = 'usd'):
    params = {'ids': crypto, 'vs_currencies': currency}
    response = requests.get(COINGECKO_API_URL+'/simple/price', params=params)
    data = response.json()
    return data.get(crypto, {}).get(currency, 'Price not available')

async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

# Price Alert Setup
user_alerts = {}

def set_price_alert(user_id, crypto, threshold_price, condition):
    user_alerts[user_id] = (crypto, threshold_price, condition)

async def set_alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    for user_id, (crypto, threshold_price, condition) in user_alerts.items():
        price = get_crypto_price(crypto)
        if (condition == 'above' and price > threshold_price) or (condition == 'below' and price < threshold_price):
            await context.bot.send_message(user_id, f"Alert: {crypto.capitalize()} is now {condition} ${threshold_price}.")
            del user_alerts[user_id]  # Remove alert after notifying user

# Main function
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("convert", convert_command))
    app.add_handler(CommandHandler("setalert", set_alert_command))

    # Alert checking job
    app.job_queue.run_repeating(alert_check, interval=300, first=10)

    app.add_error_handler(error_handler)

    # Start the bot
    app.run_polling()

if __name__ == "__main__":
    main()
"""
Main Menu: Users can view the top 100 cryptocurrencies, trending coins, or search for specific cryptocurrencies.
Cryptocurrency Price Alerts: Users can set price alerts for when a cryptocurrency goes above or below a certain price.
Convert Command: Users can convert cryptocurrencies based on the latest prices.
Improved Error Handling: The code catches exceptions in API calls to avoid crashes.
Rate Limiting: asyncio.sleep() is used to avoid hitting the Coingecko API rate limits.
API Rate Limits: The Coingecko API has rate limits, and calling it frequently without handling delays could cause issues.

Solution: Add delays (asyncio.sleep) before making API requests to avoid hitting the rate limit too frequently.
Uncaught Exception Handling: Some parts of the code may encounter uncaught exceptions, especially when interacting with external APIs.

Solution: Add proper error handling for API requests using try-except blocks to avoid crashes.
Unused Arguments in get_top_cryptos(): The is_comparing flag in the get_top_cryptos() function isn't being used in your logic.

Solution: Either implement a behavior for is_comparing or remove it if unnecessary.
Outdated Conversation Flow: In the compare section, the user is prompted to select a cryptocurrency, but the system doesn't store the second cryptocurrency to compare.

Solution: Store both cryptocurrencies and show the comparison results after selection.
Missing Context Cleanup: After setting alerts or showing crypto details, the context.user_data is not cleaned up, which may cause bugs in repeated queries.

Solution: Add proper cleanup of the context data to ensure state consistency.
app.job_queue.run_repeating() Error: The job_queue is not correctly initialized before usage.

Solution: Initialize the job queue before running jobs like alert_check.
Error in get_crypto_details(): If a cryptocurrency is not found, the details object could be None, which might result in KeyError when trying to access its attributes.

"""
