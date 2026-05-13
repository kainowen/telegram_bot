print("Importing Packages...")
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# LangChain Imports
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_classic.memory import ConversationSummaryBufferMemory
from langchain_core.messages import get_buffer_string
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_core.messages.utils import trim_messages
#Import DuckDuckGo Function
from duckduckgo_search import DDGS
# RAG imports
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

#image generation modules:
import aiohttp
import base64
import asyncio
from io import BytesIO
import time # For timing the generation

from tools import web_search

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


# =================================================

# Load system prompt from file or use default
class ToggleSystemPropmt:
    '''Allows for toggling between different system prompts'''
  
    PERSONALITY = ""

    def __init__(self):
        self.index = 1
        self.personalities = PERSONALITIES.split(";")
  
    SYSTEM_PROMPT = ""

    def __call__(self):
        if self.index == 0:
            self.index = 1
        else: 
            self.index = 0
        PERSONALITY = self.personalities[self.index]    

        print(PERSONALITY)

        if not os.path.exists(PERSONALITY):
            SYSTEM_PROMPT =  """You are MARX, a helpful, friendly, and casual AI assistant. 
                        Keep answers brief and easy to understand. Avoid unnecessary fluff. 
                        Let me know if you don't know the answer to something. Don't make things up."""
        else:
            with open(PERSONALITY, 'r') as f:
                SYSTEM_PROMPT=  f.read()
        return(SYSTEM_PROMPT)        


togglePrompt = ToggleSystemPropmt()
SYSTEM_PROMPT = togglePrompt()


async def toggle(update, context):
    #Redefines the system Prompt
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = togglePrompt()


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

# ================= MEMORY MANAGER =================
# We'll use ConversationSummaryBufferMemory with SQL as the underlying store
# This combines efficient summarization with persistent storage

class SQLBackedSummaryMemory:
    """
    A wrapper that combines ConversationSummaryBufferMemory with SQL persistence.
    This gives you the best of both worlds:
    - Summarization to manage context window
    - Persistent storage in SQL database
    """
    
    def __init__(self, session_id: str, llm, max_token_limit=1000):
        self.session_id = session_id
        self.llm = llm
        self.max_token_limit = max_token_limit
        
        # Load existing history from SQL
        self.history = get_session_history(session_id)
        
        # Create the summary memory with the loaded history
        self.memory = ConversationSummaryBufferMemory(
            llm=llm,
            max_token_limit=max_token_limit,
            return_messages=True,
            chat_memory=self.history  # This links SQL storage to the memory
        )
    
    def load_memory_variables(self, inputs):
        """Return the memory variables (the conversation summary + recent history)."""
        return self.memory.load_memory_variables(inputs)
    
    def save_context(self, inputs, outputs):
        """Save the conversation context to both memory and SQL."""
        self.memory.save_context(inputs, outputs)
    
    def clear(self):
        """Clear all memory for this session."""
        self.memory.clear()
        clear_session_history(self.session_id)
    
    @property
    def chat_memory(self):
        """Access the underlying SQL chat memory."""
        return self.history

# Dictionary to store memory instances per user
user_memories = {}

def get_conversation_memory(user_id: str, llm):
    """Retrieves or creates a SQL-backed memory for a specific user."""
    if user_id not in user_memories:
        user_memories[user_id] = SQLBackedSummaryMemory(
            session_id=user_id,
            llm=llm,
            max_token_limit=1000
        )
    return user_memories[user_id]

# ================= RAG SETUP =================

class DocumentQnA:
    """Handles Retrieval-Augmented Generation (RAG) for querying local documents."""
    
    def __init__(self):
        self.is_available = False
        self.retriever = None
        self.rag_chain = None
        
        if not os.path.exists(CHROMA_DB_PATH):
            print("⚠️ RAG not available: No vector database found.")
            return
        
        try:
            embeddings = OllamaEmbeddings(
                base_url=OLLAMA_BASE_URL,
                model=EMBEDDING_MODEL
            )
            
            vector_store = Chroma(
                persist_directory=CHROMA_DB_PATH,
                embedding_function=embeddings
            )
            
            self.retriever = vector_store.as_retriever(search_kwargs={"k": 4})
            self.is_available = True
            print("✅ RAG system loaded!")
        except Exception as e:
            print(f"⚠️ RAG initialization failed: {e}")
    
    def query(self, question: str) -> str:
        """Query the document database with a question."""
        if not self.is_available:
            return "📚 Document Q&A is not available."
        
        try:
            # For RAG, we'll use a simple prompt without memory
            llm = ChatOllama(
                base_url=OLLAMA_BASE_URL,
                model=TARGET_MODEL,
                temperature=0.3,
            )
            
            docs = self.retriever.invoke(question)
            context = "\n\n---\n\n".join([doc.page_content for doc in docs])

            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are MARX. Answer based ONLY on the context below.
                    If unsure, say "I couldn't find that in the documentation."

                Context: {context}"""),
                ("human", "{question}")
            ])

            chain = prompt | llm | StrOutputParser()
            return chain.invoke({"context": context, "question": question})
            
        except Exception as e:
            return f"❌ RAG query failed: {str(e)}"

rag_system = DocumentQnA()


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

async def askdocs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /askdocs command."""
    question = " ".join(context.args)
    
    if not question:
        await update.message.reply_text(
            "📚 Please provide a question!\n"
            "Example: /askdocs How do I configure the API?"
        )
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    answer = rag_system.query(question)
    await update.message.reply_text(f"📚 **Documentation Answer:**\n\n{answer}")


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
    app.add_handler(CommandHandler("askdocs", askdocs_command))
    app.add_handler(CommandHandler("search", web_search.search_command))
    app.add_handler(CommandHandler("news", web_search.news_command))
    app.add_handler(CommandHandler("toggle", toggle))
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