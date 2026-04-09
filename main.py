import json
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from collections import defaultdict
import data.api_key

# ================= CONFIGURATION =================
TELEGRAM_BOT_TOKEN = data.api_key.api_key # From @BotFather
OLLAMA_URL = "http://192.168.178.43:11434/api/generate" # Your server's IP
OLLAMA_MODEL = "llama3.2" # Or any model you have pulled
# =================================================

# System prompt - defines the bot's personality and behavior
SYSTEM_PROMPT = """You are a helpful, friendly, and casual and concise AI assistant.
You provide accurate information and admit when you don't know something. You keep answers breif and easy to understand.
You keep responses clear and avoid unnecessary fluff."""

# Store conversation history per user (max messages to remember)
MAX_HISTORY = 10 # Remembers last 5 exchanges (10 messages total)
conversation_history = defaultdict(list) # Automatically creates empty lists per user
# =================================================

def build_prompt(user_id: int, new_message: str) -> str:
    """Build a complete prompt with system prompt and conversation history"""
    # Start with system prompt
    full_prompt = f"<|system|>\n{SYSTEM_PROMPT}\n\n"

    # Add conversation history
    full_prompt += "<|history|>\n"
    for message in conversation_history[user_id]:
        full_prompt += f"User: {message['user']}\nAssistant: {message['assistant']}\n"

    # Add current message
    full_prompt += f"<|current|>\nUser: {new_message}\nAssistant: "

    return full_prompt

def update_history(user_id: int, user_msg: str, assistant_msg: str):
    """Store the conversation in memory, keeping only last MAX_HISTORY messages"""
    conversation_history[user_id].append({
        "user": user_msg,
        "assistant": assistant_msg
    })

    # Keep only the most recent messages
    if len(conversation_history[user_id]) > MAX_HISTORY:
        conversation_history[user_id].pop(0)

def clear_history(user_id: int):
    """Clear conversation history for a user"""
    conversation_history[user_id] = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when /start is issued."""
    user_id = update.effective_user.id
    clear_history(user_id)

    await update.message.reply_text(
        "🤖 Hello! I'm your local AI assistant with memory!\n\n"
        "I remember our recent conversation so we can have natural back-and-forth.\n\n"
        f"I'll remember the last {MAX_HISTORY // 2} exchanges.\n\n"
        "Commands:\n"
        "/start - Reset our conversation\n"
        "/clear - Clear conversation history\n"
        "/status - Show current memory status"
    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear conversation history for this user"""
    user_id = update.effective_user.id
    clear_history(user_id)
    await update.message.reply_text("🧹 Conversation history cleared! Starting fresh.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current memory usage"""
    user_id = update.effective_user.id
    history_count = len(conversation_history[user_id])
    await update.message.reply_text(
        f"📊 Memory Status:\n"
        f"Messages stored: {history_count}\n"
        f"Max capacity: {MAX_HISTORY}\n"
        f"Conversations remembered: {history_count // 2}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages with conversation memory"""
    user_message = update.message.text
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Send a "typing" indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Build prompt with history
        full_prompt = build_prompt(user_id, user_message)

        # Call Ollama API
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7, # Controls creativity (0.0-1.0)
                    "top_p": 0.9, # Nucleus sampling
                    "num_predict": 256 # Max tokens to generate
                }
            },
            timeout=90
        )

        if response.status_code == 200:
            result = response.json()
            bot_reply = result.get("response", "Sorry, I couldn't generate a response.")

            # Store in memory (user message and assistant response)
            update_history(user_id, user_message, bot_reply)

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
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running with memory and system prompt...")
    print(f"Memory will keep last {MAX_HISTORY // 2} exchanges per user")
    app.run_polling()

if __name__ == "__main__":
    print("Starting Telegram bot with Ollama (with memory!)...")
    main()
