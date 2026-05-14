print("Importing Packages...")
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# LangChain Imports
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import get_buffer_string
from langchain_core.messages.utils import trim_messages

load_dotenv(override=True)


# ================= CONFIGURATION =================
TELEGRAM_BOT_TOKEN = os.getenv('api_key')
OLLAMA_BASE_URL = os.getenv('Ollama_URL')
TARGET_MODEL = os.getenv('TARGET_MODEL')
PERSONALITY = os.getenv('PERSONALITY')
PERSONALITIES = os.getenv('PERSONALITIES')

# SQLite database for conversation history
DATABASE_URL = os.getenv('DATABASE_URL')

# RAG Configuration
DOCS_DIRECTORY = os.getenv('DOCS_DIRECTORY')
CHROMA_DB_PATH = os.getenv('CHROMA_DB_PATH')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL')


# ================= SQL HISTORY SETUP =================

def get_session_history(session_id: str):
    """
    Creates or retrieves a SQL-based chat history for a specific user.
    This stores raw message history in the database.
    """
    return SQLChatMessageHistory(
        session_id=session_id,
        connection=DATABASE_URL
    )

def clear_session_history(session_id: str):
    """Clears conversation history for a specific user from the database."""
    history = get_session_history(session_id)
    history.clear()

# ================= GENERATE CODE =================

async def code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates a section of code based on a request in telegram and writes it to a tool.py file."""
    user_message = update.message.text.replace("/code","")
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    SYSTEM_PROMPT = "You are a Python script generator. Your goal is to provide functional, concise code based on user requests.\
                    STRICT RULES:\
                    Output ONLY valid Python code.\
                    Do NOT use Markdown formatting (no ```python blocks).\
                    Do NOT provide explanations, greetings, or commentary.\
                    Ensure the code is self-contained and runnable."

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
    try:
       # Initialize LLM
        llm = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=TARGET_MODEL,
            temperature=0.7,
        )
        
        
        # Create ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", "{input}")  # This tells LangChain where to inject user_message
        ])
        
        # Create chain
        chain = ( prompt 
                | llm 
                | StrOutputParser()
                )


        # Invoke with the user's code request
        bot_reply = chain.invoke(
            {"input": user_message},
            config={"configurable": {"session_id": user_id}}
            )

        #Write code to temp tool.py file
        tool_path = "temp_utilities/tool.py"
        if os.path.exists(tool_path):
            with open(tool_path, "w") as file:
                file.write(bot_reply)

            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ================= TELEGRAM BOT HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = str(update.effective_user.id)
    
    # Clear memory for this user
    if user_id in user_memories:
        user_memories[user_id].clear()
    else:
        clear_session_history(user_id)
    
    await update.message.reply_text(
        "🤖 Hey, how can I help you today...\n\n"
        "Commands:\n"
        "/start - Reset our conversation\n"
        "/clear - Clear conversation memory\n"
        "/askdocs <question> - Query my documentation\n"
        "/status - Show current status"
        "/search <question> - Search the internet for an answer\n"
        "/news - Search the internet for relevant news"
        "/code - Generate a .py file containing a tool"

    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command."""
    user_id = str(update.effective_user.id)
    
    if user_id in user_memories:
        user_memories[user_id].clear()
    else:
        clear_session_history(user_id)
    
    await update.message.reply_text("🧹 Memory wiped! Starting fresh.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    user_id = str(update.effective_user.id)
    history = get_session_history(user_id)
    message_count = len(history.messages)
    
    status_text = f"""📊 Bot Status:
    
• Model: {TARGET_MODEL}
• Messages in SQL: {message_count}
• RAG: {'✅ Available' if rag_system.is_available else '❌ Not available'}
• Memory type: SQL + Summary Buffer

To use document Q&A: /askdocs your question here"""
    
    await update.message.reply_text(status_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages with memory."""
    user_message = update.message.text
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    #print(SYSTEM_PROMPT)
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        # Initialize LLM
        llm = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=TARGET_MODEL,
            temperature=0.7,
        )
        
        # Get or create memory for this user (SQL-backed summary memory)
        memory = get_conversation_memory(user_id, llm)
        
        # Create ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        
        #Initialise the Trimmer to reduce the prompt length
        trimmer = trim_messages(
            max_tokens=3000,
            strategy="last",
            token_counter=llm,
            include_system=True,
            start_on="human"
        )


        # Create chain
        chain = (
            {
                "history": lambda x: trimmer.invoke(x.get("history", [])),
                "input": lambda x: x["input"]
            }
                 | prompt 
                 | llm 
                 | StrOutputParser()
                )
        
        # Wrap with history using RunnableWithMessageHistory
        # This automatically saves messages to SQL
        chain_with_history = RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )
        
        # Invoke with the user's message
        bot_reply = chain_with_history.invoke(
            {"input": user_message},
            config={"configurable": {"session_id": user_id}}
        )
        
        await update.message.reply_text(bot_reply)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ================= MAIN ENTRY POINT =================

def main():
    """Start the Telegram bot."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("code", code))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    
    print("🤖 Bot is starting...")
    print(f"   Model: {TARGET_MODEL}")
    print(f"   Ollama URL: {OLLAMA_BASE_URL}")
    print(f"   SQL Database: {DATABASE_URL}")
    print("\n🤖 Ready!")
    
    app.run_polling()

if __name__ == "__main__":
    main()