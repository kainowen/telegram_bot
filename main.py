import os
import json
from dotenv import load_dotenv, dotenv_values
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# LangChain Imports
from langchain_ollama import OllamaLLM
from langchain_classic.chains import ConversationChain
from langchain_classic.memory import ConversationBufferWindowMemory, ConversationSummaryBufferMemory
from langchain_classic.prompts import PromptTemplate
from langchain_community.chat_message_histories import FileChatMessageHistory, SQLChatMessageHistory

#Load Environmentat Variables
load_dotenv()

# ================= CONFIGURATION =================
TELEGRAM_BOT_TOKEN = os.getenv('api_key')
OLLAMA_BASE_URL = os.getenv('OllAMA_URL') # Base URL for LangChain
TARGET_MODEL = os.getenv('TARGET_MODEL')

# Dictionary to store a unique memory object for every user
user_memories = {}

#Retrieve Personality definition
if not os.path.exists("data/personality.txt"):
    # System prompt
    SYSTEM_PROMPT = """You are MARX, a helpful, friendly, and casual AI assistant. Keep answers brief and easy to understand. Avoid unnecessary fluff. LEt me know if you don't know the answer to something. Don't make things up."""
else:
    with open("data/personality.txt", 'r') as f:
        SYSTEM_PROMPT = f.read()

#Complete system Prompt    
SYSTEM_PROMPT = SYSTEM_PROMPT + """ Current conversation:
{history}
User: {input}
Assistant:"""

# =================================================

def get_conversation_chain(user_id: int):
    """Retrieves or creates a LangChain ConversationChain for a specific user."""
    if user_id not in user_memories:
        # 1. Initialize the LLM
        llm = OllamaLLM(
            base_url=OLLAMA_BASE_URL,
            model=TARGET_MODEL,
            temperature=0.7
        )

        # 2. Setup Memory (k=5 means last 5 exchanges)
        memory = ConversationSummaryBufferMemory(
            llm=llm, 
            max_token_limit=1000, 
            memory_key="history",
            return_messages=False # Set to True if using ChatPromptTemplate"
        )


        # 3. Setup the Prompt
        prompt = PromptTemplate(
            input_variables=["history", "input"],
            template=SYSTEM_PROMPT
        )

        # 4. Create the Chain
        user_memories[user_id] = ConversationChain(
            llm=llm,
            memory=memory,
            prompt=prompt,
            verbose=True # Useful for debugging in console
        )

        """#store memory
        if not os.path.exists(f"chat_histories/telegram_user_{user_id}.json"):
            with open(f"chat_histories/telegram_user_{user_id}.json", 'w') as file:
                file.write("")

        with open(f"chat_histories/telegram_user_{user_id}.json", 'w') as file:
            json.dump(user_memories[user_id].to_json(), file)"""

    return user_memories[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_memories:
        user_memories[user_id].memory.clear()
    
    await update.message.reply_text("🤖 Hey, how can I help you today...")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_memories:
        user_memories[user_id].memory.clear()
    await update.message.reply_text("🧹 Memory wiped!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # Get the specific chain for this user
        conversation = get_conversation_chain(user_id)
        
        # Run the chain (this automatically pulls history and updates it)
        bot_reply = conversation.predict(input=user_message)

        await update.message.reply_text(bot_reply)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Hey, how can I help you today...")
    app.run_polling()

if __name__ == "__main__":
    main()