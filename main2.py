print("Importing Packages...")
import os
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# LangChain Imports - Updated for 2026
from langchain_ollama import ChatOllama  # Changed from OllamaLLM (better for chat)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

# RAG imports (for document Q&A)
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

load_dotenv()

# ================= CONFIGURATION =================
TELEGRAM_BOT_TOKEN = os.getenv('api_key')
OLLAMA_BASE_URL = os.getenv('OllAMA_URL')
TARGET_MODEL = os.getenv('TARGET_MODEL')

# SQLite database for conversation history
DATABASE_URL = "sqlite:///chat_histories/chat_history.db"

# RAG Configuration
DOCS_DIRECTORY = "./docs"           # Folder containing your documentation
CHROMA_DB_PATH = "./chroma_db"      # Vector database location
EMBEDDING_MODEL = "nomic-embed-text" # Model for creating embeddings

# =================================================

# Load system prompt from file or use default
def load_system_prompt():
    """Load the system prompt from personality.txt or use default."""
    if not os.path.exists("data/personality.txt"):
        return """You are MARX, a helpful, friendly, and casual AI assistant. 
Keep answers brief and easy to understand. Avoid unnecessary fluff. 
Let me know if you don't know the answer to something. Don't make things up."""
    else:
        with open("data/personality.txt", 'r') as f:
            return f.read()

SYSTEM_PROMPT = load_system_prompt()

# ================= SQL MEMORY SETUP =================

def get_session_history(session_id: str):
    """
    Creates or retrieves a SQL-based chat history for a specific user.
    This replaces the FileChatMessageHistory with proper database persistence.
    
    Args:
        session_id: Unique identifier (uses Telegram user_id as string)
    
    Returns:
        SQLChatMessageHistory object that persists to conversations.db
    """
    return SQLChatMessageHistory(
        session_id=session_id,
        connection_string=DATABASE_URL  # Creates conversations.db if it doesn't exist
    )

def clear_session_history(session_id: str):
    """
    Clears conversation history for a specific user from the database.
    
    Args:
        session_id: The user's Telegram ID as string
    """
    history = get_session_history(session_id)
    history.clear()  # SQLChatMessageHistory has a built-in clear() method

# ================= RAG SETUP =================

class DocumentQnA:
    """
    Handles Retrieval-Augmented Generation (RAG) for querying local documents.
    This class loads the vector database once at startup and provides query capability.
    """
    
    def __init__(self):
        """Initialize the RAG system by loading the existing vector database."""
        self.is_available = False
        self.retriever = None
        self.rag_chain = None
        
        # Check if vector database exists
        if not os.path.exists(CHROMA_DB_PATH):
            print("⚠️ RAG not available: No vector database found. Run build_vector_db.py first.")
            return
        
        try:
            # Load embedding model (needed to convert questions to vectors)
            embeddings = OllamaEmbeddings(
                base_url=OLLAMA_BASE_URL,
                model=EMBEDDING_MODEL
            )
            
            # Load existing vector store (like opening a SQL database)
            vector_store = Chroma(
                persist_directory=CHROMA_DB_PATH,
                embedding_function=embeddings
            )
            
            # Create retriever that finds top 4 most relevant chunks
            self.retriever = vector_store.as_retriever(
                search_kwargs={"k": 4}
            )
            
            # Initialize LLM for answering (lower temperature for factual responses)
            self.llm = ChatOllama(
                base_url=OLLAMA_BASE_URL,
                model=TARGET_MODEL,
                temperature=0.3,  # Lower = more factual, less creative
            )
            
            # Create RAG prompt template
            rag_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are MARX, a technical assistant. Answer based ONLY on the provided context.
If the context doesn't contain the answer, say "I couldn't find that in the documentation."
Keep answers brief and helpful.

Context:
{context}"""),
                ("human", "{question}")
            ])
            
            # Helper function to format retrieved documents
            def format_docs(docs):
                return "\n\n---\n\n".join([doc.page_content for doc in docs])
            
            # Build RAG chain: retrieve context -> format -> prompt -> llm -> output
            from langchain_core.runnables import RunnablePassthrough
            self.rag_chain = (
                {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
                | rag_prompt
                | self.llm
                | StrOutputParser()
            )
            
            self.is_available = True
            print("✅ RAG system loaded and ready!")
            
        except Exception as e:
            print(f"⚠️ RAG initialization failed: {e}")
    
    def query(self, question: str) -> str:
        """
        Query the document database with a question.
        
        Args:
            question: User's question about the documentation
            
        Returns:
            Answer based on the documentation
        """
        if not self.is_available:
            return "📚 Document Q&A is not available. Please run build_vector_db.py first."
        
        try:
            answer = self.rag_chain.invoke(question)
            return answer
        except Exception as e:
            return f"❌ RAG query failed: {str(e)}"

# Initialize RAG system once at startup
rag_system = DocumentQnA()

# ================= TELEGRAM BOT HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - resets conversation and shows welcome message."""
    user_id = str(update.effective_user.id)
    
    # Clear the user's conversation history from SQL database
    clear_session_history(user_id)
    
    await update.message.reply_text(
        "🤖 Hey, how can I help you today...\n\n"
        "Commands:\n"
        "/start - Reset our conversation\n"
        "/clear - Clear conversation memory\n"
        "/askdocs <question> - Query my documentation (e.g., /askdocs How do I install?)\n"
        "/status - Show current status"
    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command - wipes conversation memory for this user."""
    user_id = str(update.effective_user.id)
    clear_session_history(user_id)
    await update.message.reply_text("🧹 Memory wiped! Starting fresh.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - shows bot status and memory info."""
    user_id = str(update.effective_user.id)
    
    # Get history to check if it exists
    history = get_session_history(user_id)
    message_count = len(history.messages)
    
    status_text = f"""📊 Bot Status:
    
• Model: {TARGET_MODEL}
• Memory: {message_count} messages stored in SQL database
• RAG: {'✅ Available' if rag_system.is_available else '❌ Not available'}
• Ollama URL: {OLLAMA_BASE_URL}

To use document Q&A, type: /askdocs your question here"""
    
    await update.message.reply_text(status_text)

async def askdocs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /askdocs command - queries local documentation using RAG.
    Usage: /askdocs How do I configure the API?
    """
    # Extract the question from the command (everything after /askdocs)
    question = " ".join(context.args)
    
    if not question:
        await update.message.reply_text(
            "📚 Please provide a question!\n\n"
            "Example: /askdocs How do I set up authentication?"
        )
        return
    
    # Send typing indicator (RAG might take a few seconds)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Query the documentation
    answer = rag_system.query(question)
    await update.message.reply_text(f"📚 **Documentation Answer:**\n\n{answer}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle regular text messages - uses ChatPromptTemplate with SQL memory.
    This is the main chat handler for conversation with the AI.
    """
    user_message = update.message.text
    user_id = str(update.effective_user.id)  # Convert to string for session_id
    chat_id = update.effective_chat.id
    
    # Send typing indicator so user knows bot is working
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        # ================= SETUP LLM WITH CHAT PROMPT TEMPLATE =================
        
        # 1. Initialize Ollama Chat model (better for conversation than OllamaLLM)
        llm = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=TARGET_MODEL,
            temperature=0.7,
        )
        
        # 2. Create ChatPromptTemplate with proper message roles
        #    This is better than PromptTemplate because it maintains system/human/ai roles
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),           # System message (bot personality)
            MessagesPlaceholder(variable_name="history"),  # Previous conversation goes here
            ("human", "{input}")                 # Current user message
        ])
        
        # 3. Create base chain: prompt -> llm -> string output
        chain = prompt | llm | StrOutputParser()
        
        # 4. Wrap chain with SQL message history
        #    This automatically loads previous messages and saves new ones
        chain_with_history = RunnableWithMessageHistory(
            chain,
            get_session_history,                 # Function that returns SQL history for a user
            input_messages_key="input",          # Key for user's current message
            history_messages_key="history",      # Key where history is injected
        )
        
        # 5. Invoke the chain with the user's message
        #    The config passes the session_id so it knows which user's history to use
        bot_reply = chain_with_history.invoke(
            {"input": user_message},
            config={"configurable": {"session_id": user_id}}
        )
        
        # Send the response back to the user
        await update.message.reply_text(bot_reply)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ================= MAIN ENTRY POINT =================

def main():
    """Start the Telegram bot."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("askdocs", askdocs_command))
    
    # Register message handler (for regular chat)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot is starting...")
    print(f"   Model: {TARGET_MODEL}")
    print(f"   Ollama URL: {OLLAMA_BASE_URL}")
    print(f"   SQL Database: {DATABASE_URL}")
    print(f"   RAG Available: {rag_system.is_available}")
    print("\n🤖 Ready! Send messages to your Telegram bot...")
    
    # Start polling for updates
    app.run_polling()

if __name__ == "__main__":
    main()