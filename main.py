print("Importing Packages...")
import os
import re
from dotenv import load_dotenv
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import telegramify_markdown
from pathlib import Path

#Custom imports
from functions import toggleSystemPrompt, web_search, projectMemory,generate_code,rag_recall,photo_analyzer,process_docs

# LangChain Imports
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages.utils import trim_messages

print("Loading Environmental variables...")
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


# ======================DEFINE SYSTEM PROMPT/PERSONALITY===========================

# Load system prompt from file or use default
togglePrompt = toggleSystemPrompt.ToggleSystemPropmt(PERSONALITIES=PERSONALITIES)
SYSTEM_PROMPT = togglePrompt(PERSONALITIES=PERSONALITIES)
SYSTEM_PROMPT = f"{SYSTEM_PROMPT} \n Current Date: {datetime.datetime.now()}"
SYSTEM_PERSONALITY = togglePrompt.getName()
user_memories = {} #Creates container for conversation memory


# ================= RAG SETUP =================

rag_system = rag_recall.DocumentQnA(CHROMA_DB_PATH,OLLAMA_BASE_URL,EMBEDDING_MODEL,TARGET_MODEL) #Load class called for RAG

# ================= TELEGRAM BOT HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = str(update.effective_user.id)
    
    # Clear memory for this user
    if user_id in user_memories:
        user_memories[user_id].clear()
    else:
        projectMemory.clear_session_history(user_id, DATABASE_URL,SYSTEM_PERSONALITY)
    
    await update.message.reply_text(
        "🤖 Hey, how can I help you today...\n\n"
        "Commands:\n"
        "/start - Reset our conversation\n"
        "/clear - Clear conversation memory\n"
        "/askdocs <question> - Query my documentation\n"
        "/status - Show current status"
        "/search <question> - Search the internet for an answer\n"
        "/news - Search the internet for relevant news"
        "/code - generate a simple python file"

    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command."""
    user_id = str(update.effective_user.id)
    
    if user_id in user_memories:
        user_memories[user_id].clear()
    else:
        projectMemory.clear_session_history(session_id=user_id, DATABASE_URL=DATABASE_URL,personality=SYSTEM_PERSONALITY)
    
    await update.message.reply_text("🧹 Memory wiped! Starting fresh.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    print("Starting: status_command...")
    user_id = str(update.effective_user.id)
    history = projectMemory.get_session_history(session_id=user_id,DATABASE_URL=DATABASE_URL,personality=SYSTEM_PERSONALITY)
    message_count = len(history.messages)
    
    status_text = f"""📊 Bot Status:
                        
    • Model: {TARGET_MODEL}
    • Messages in SQL: {message_count}
    • RAG: {'✅ Available' if rag_system.is_available else '❌ Not available'}
    • Personality: {SYSTEM_PERSONALITY}"""
    
    await update.message.reply_text(status_text)

async def askdocs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /askdocs command."""
    question = " ".join(context.args)
    
    if not question:
        await update.message.reply_text(
            "📚 Please provide a question!\n"
            "Example: /askdocs How do I configure the API?"
        )
        return
    
    processing_msg = await update.message.reply_text("🧠 Thinking...")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    answer = rag_system.query(question,SYSTEM_PROMPT=SYSTEM_PROMPT)
    await processing_msg.delete()
    await update.message.reply_text(f"📚 **Documentation Answer:**\n\n{answer}")

async def telldocs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Takes documents passed through telegram and populates chromadb"""
    print("Starting telldocs_command...")
    doc = update.message.document
    doc_name = doc.file_name
    file_save_path = str(Path(__file__).resolve().parent / os.getenv('DOCS_DIRECTORY') / doc_name)
    archive_path = str(Path(__file__).resolve().parent / os.getenv('DOCS_DIRECTORY') / ".archive"  /doc_name)
    status_message = await update.message.reply_text(f"📁 Downloading '{doc_name}'")

    try:
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive((file_save_path))
        await status_message.edit_text(f"✅Succesfully downloaded '{doc_name}' to {DOCS_DIRECTORY}")
    except Exception as e:
        print(e)
        await status_message.edit_text(f"❌An error occurred: {e}")

    process_docs.build_database()

    print("Archiving File")
    os.rename(file_save_path,archive_path)  #Move file to .archive

async def toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #Redefines the system Prompt
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = togglePrompt(PERSONALITIES=PERSONALITIES)
    SYSTEM_PROMPT = f"{SYSTEM_PROMPT} \n Current Date: {datetime.datetime.now()}"
    global SYSTEM_PERSONALITY
    SYSTEM_PERSONALITY = togglePrompt.getName()
    await update.message.reply_text(f"Successfuly Switched to Personality: {SYSTEM_PERSONALITY}")

def code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return generate_code.code(update, context, OLLAMA_BASE_URL=OLLAMA_BASE_URL, TARGET_MODEL=TARGET_MODEL)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages with memory."""
    print("Starting: handle_message...")
    user_message = update.message.text
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id


    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    # Send a processing message since this takes time
    processing_msg = await update.message.reply_text("🧠 Thinking...")

    try:
        # Initialize LLM
        llm = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=TARGET_MODEL,
            temperature=0.7,
            reasoning=True
        )

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

        def get_session_history_wrapper():
            '''Wraps the get_session_history function so that it can be passed into the chain_with_history runnable '''
            return projectMemory.get_session_history(session_id=user_id, DATABASE_URL=DATABASE_URL,personality=SYSTEM_PERSONALITY)

        chain_with_history = RunnableWithMessageHistory(
            chain,
            get_session_history=get_session_history_wrapper,
            input_messages_key="input",
            history_messages_key="history",
        )
        
        # Invoke with the user's message
        bot_reply = chain_with_history.invoke(
            {"input": user_message},
            config={"configurable": {"session_id": user_id}}
        )
        
        await processing_msg.delete()
        await update.message.reply_text(telegramify_markdown.markdownify(str(bot_reply)), parse_mode="MarkdownV2")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

def analyse_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_memories = projectMemory.get_session_history(session_id=str(update.effective_user.id),DATABASE_URL=DATABASE_URL,personality=SYSTEM_PERSONALITY)
    return photo_analyzer.analyze_image(update,context, OLLAMA_BASE_URL=OLLAMA_BASE_URL,SYSTEM_PROMPT=SYSTEM_PROMPT,TARGET_MODEL=TARGET_MODEL,DATABASE_URL=DATABASE_URL,user_memories=user_memories,PERSONALITY=SYSTEM_PERSONALITY)
# ================= MAIN ENTRY POINT =================

def main():
    """Start the Telegram bot."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("askdocs", askdocs_command))
    app.add_handler(CommandHandler("telldocs", telldocs_command))
    app.add_handler(CommandHandler("search", web_search.search_command))
    app.add_handler(CommandHandler("news", web_search.news_command))
    app.add_handler(CommandHandler("code", code))
    app.add_handler(CommandHandler("toggle", toggle))
    app.add_handler(MessageHandler(filters.PHOTO, analyse_photo))
    app.add_handler(MessageHandler(filters.ATTACHMENT, telldocs_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    
    print("🤖 Bot is starting...")
    print(f"   Model: {TARGET_MODEL}")
    print(f"   Ollama URL: {OLLAMA_BASE_URL}")
    print(f"   SQL Database: {DATABASE_URL}")
    print(f"   RAG Available: {rag_system.is_available}")
    print("\n🤖 Ready!")
    
    app.run_polling()

if __name__ == "__main__":
    main()