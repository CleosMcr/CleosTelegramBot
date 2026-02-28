import threading
import os
import time
from flask import Flask

# ==========================
# HEALTH CHECK SERVER (CRITICAL FOR RENDER)
# ==========================

# Create Flask app for health checks
health_app = Flask(__name__)

@health_app.route('/')
@health_app.route('/health')
@health_app.route('/healthz')
def health():
    return 'OK', 200

def run_health_server():
    """Run Flask server in a separate thread"""
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting health check server on port {port}...")
    health_app.run(host='0.0.0.0', port=port)

# Start health server in background
health_thread = threading.Thread(target=run_health_server, daemon=True)
health_thread.start()
print("✅ Health check server started - Render will now detect the open port")

# Give the server a moment to start
time.sleep(2)

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import base64

# ==========================
# CONFIGURATION - ALL FROM ENV VARS
# ==========================

# Get configuration from environment variables (NO hardcoded fallbacks!)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables")

SHEET_NAME = os.environ.get('SHEET_NAME')
if not SHEET_NAME:
    raise ValueError("No SHEET_NAME found in environment variables")

# ==========================
# GOOGLE SHEETS SETUP
# ==========================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

def get_google_credentials():
    """Get Google credentials from environment variables only"""
    
    # Try base64 encoded credentials (recommended for Render)
    if os.environ.get('GOOGLE_CREDENTIALS_BASE64'):
        try:
            encoded_creds = os.environ.get('GOOGLE_CREDENTIALS_BASE64')
            decoded_creds = base64.b64decode(encoded_creds).decode('utf-8')
            credentials_info = json.loads(decoded_creds)
            print("✅ Using base64 encoded credentials from env var")
            return ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
        except Exception as e:
            print(f"❌ Error loading base64 credentials: {e}")
            raise
    
    # Try JSON string from environment variable
    elif os.environ.get('GOOGLE_CREDENTIALS'):
        try:
            credentials_info = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
            print("✅ Using JSON credentials from env var")
            return ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
        except Exception as e:
            print(f"❌ Error loading JSON credentials: {e}")
            raise
    
    else:
        raise Exception("No Google credentials found in environment variables! Set GOOGLE_CREDENTIALS_BASE64 or GOOGLE_CREDENTIALS")

try:
    # Get credentials
    creds = get_google_credentials()
    
    # Print service account email for verification
    if hasattr(creds, 'service_account_email'):
        print(f"🔑 Using service account: {creds.service_account_email}")
    
    # Authorize and open sheet
    client = gspread.authorize(creds)
    
    # Optional: See all available sheets (helpful for debugging)
    try:
        all_sheets = client.openall()
        if all_sheets:
            print(f"Available sheets: {[sheet.title for sheet in all_sheets]}")
    except Exception as e:
        print(f"Note: Could not list all sheets: {e}")
    
    sheet = client.open(SHEET_NAME).sheet1
    print(f"✅ Successfully connected to sheet: {SHEET_NAME}")
    
except Exception as e:
    print(f"❌ Failed to connect to Google Sheets: {e}")
    print("Make sure you've set up GOOGLE_CREDENTIALS_BASE64 or GOOGLE_CREDENTIALS in Render env vars")
    raise

# ==========================
# STATES
# ==========================

CASH, CARD, UBER, DELIVEROO, APP = range(5)

# ==========================
# HELPERS
# ==========================

def is_number(value):
    try:
        float(value)
        return True
    except:
        return False

# ==========================
# CONVERSATION FLOW
# ==========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter Cash amount:")
    return CASH


async def cash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text
    if not is_number(value):
        await update.message.reply_text("❌ Please enter a valid number for Cash.")
        return CASH

    context.user_data["Cash"] = value
    await update.message.reply_text("Enter Card amount:")
    return CARD


async def card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text
    if not is_number(value):
        await update.message.reply_text("❌ Please enter a valid number for Card.")
        return CARD

    context.user_data["Card"] = value
    await update.message.reply_text("Enter Uber amount:")
    return UBER


async def uber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text
    if not is_number(value):
        await update.message.reply_text("❌ Please enter a valid number for Uber.")
        return UBER

    context.user_data["Uber"] = value
    await update.message.reply_text("Enter Deliveroo amount:")
    return DELIVEROO


async def deliveroo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text
    if not is_number(value):
        await update.message.reply_text("❌ Please enter a valid number for Deliveroo.")
        return DELIVEROO

    context.user_data["Deliveroo"] = value
    await update.message.reply_text("Enter App amount:")
    return APP


async def app_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text
    if not is_number(value):
        await update.message.reply_text("❌ Please enter a valid number for App.")
        return APP

    context.user_data["App"] = value

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    staff_name = update.message.from_user.full_name

    print("DEBUG: Writing to sheet:", [
        timestamp,
        staff_name,
        context.user_data["Cash"],
        context.user_data["Card"],
        context.user_data["Uber"],
        context.user_data["Deliveroo"],
        context.user_data["App"],
    ])

    try:
        sheet.append_row([
            str(timestamp),
            str(staff_name),
            str(context.user_data["Cash"]),
            str(context.user_data["Card"]),
            str(context.user_data["Uber"]),
            str(context.user_data["Deliveroo"]),
            str(context.user_data["App"]),
        ])
        await update.message.reply_text("✅ All values saved successfully!")
    except Exception as e:
        print(f"Error saving to sheet: {e}")
        await update.message.reply_text("❌ Error saving to Google Sheet. Check logs.")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Entry cancelled.")
    return ConversationHandler.END


# ==========================
# MAIN
# ==========================

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        CASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, cash)],
        CARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, card)],
        UBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, uber)],
        DELIVEROO: [MessageHandler(filters.TEXT & ~filters.COMMAND, deliveroo)],
        APP: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_amount)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(conv_handler)

print("🤖 Bot is running...")
app.run_polling()