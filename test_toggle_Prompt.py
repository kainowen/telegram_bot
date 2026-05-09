import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


load_dotenv(override=True)


# ================= CONFIGURATION =================
TELEGRAM_BOT_TOKEN = os.getenv('api_key')
OLLAMA_BASE_URL = os.getenv('Ollama_URL')
TARGET_MODEL = os.getenv('TARGET_MODEL')
PERSONALITIES = os.getenv('PERSONALITY')

# SQLite database for conversation history
DATABASE_URL = os.getenv('DATABASE_URL')

# RAG Configuration
DOCS_DIRECTORY = os.getenv('DOCS_DIRECTORY')
CHROMA_DB_PATH = os.getenv('CHROMA_DB_PATH')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL')




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
            PERSONALITY = self.personalities[self.index]
        else: 
            self.index = 0
            PERSONALITY = self.personalities[self.index]

        if not os.path.exists(PERSONALITY):
            SYSTEM_PROMPT =  """You are MARX, a helpful, friendly, and casual AI assistant. 
                        Keep answers brief and easy to understand. Avoid unnecessary fluff. 
                        Let me know if you don't know the answer to something. Don't make things up."""
        else:
            with open(PERSONALITY, 'r') as f:
                SYSTEM_PROMPT=  f.read()
        return(SYSTEM_PROMPT)
                

toggle = ToggleSystemPropmt()
SYSTEM_PROMPT = toggle()

print(SYSTEM_PROMPT)

SYSTEM_PROMPT = toggle()

print(SYSTEM_PROMPT)
