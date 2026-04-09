import json
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from collections import defaultdict

# ================= CONFIGURATION =================
TELEGRAM_BOT_TOKEN = "8663203013:AAEkK9LAIpaHkRIDZwjxgaRtLbR_rxJpz4g"
OLLAMA_URL = "http://192.168.178.43:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when /start is issued."""
    await update.message.reply_text(
        "🤖 Hello! I'm your local AI assistant.\n"
        "Just send me any message and I'll reply using my local LLM."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):  
    """Handle user messages, send to Ollama, and reply."""
    user_message = update.message.text
    chat_id = update.effective_chat.id

    # Send a "typing" indicator so the user knows the bot is working
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Call Ollama API on your network server
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": user_message,
                "stream": False # Get complete response at once
            },
            timeout=60 # Give the model time to generate
        )

        if response.status_code == 200:
            result = response.json()
            bot_reply = result.get("response", "Sorry, I couldn't generate a response.")
            await update.message.reply_text(bot_reply)
        else:
            await update.message.reply_text(f"❌ Ollama error: {response.status_code}")

    except requests.exceptions.Timeout:
        await update.message.reply_text("⏰ The AI took too long to respond. Please try again.")
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("🔌 Cannot connect to Ollama server. Is it running?")
    except Exception as e:
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")

def main():
    """Start the bot."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    print("Starting Telegram bot with Ollama...")
    asyncio.run(main())