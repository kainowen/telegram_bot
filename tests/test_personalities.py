print("Importing Packages...")
import os
from dotenv import load_dotenv
from pathlib import Path

print("Loading Environmental Variables...")
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

        folder_path = str(Path(__file__).resolve().parent.parent) + str(PERSONALITIES)
        personalityList = []
        for entry in os.scandir(folder_path):
            if entry.is_file():
               personalityList.append(entry.name)
        self.personalities = personalityList
        self.index = len(self.personalities)
  
    SYSTEM_PROMPT = ""

    def __call__(self):
        personalityCount = len(self.personalities)
        if int(self.index) >= int(personalityCount) - 1:
            self.index = 0
        else: 
            self.index += 1
        
        PERSONALITY = str(Path(__file__).resolve().parent.parent) + PERSONALITIES +  self.personalities[self.index]

        if not os.path.exists(PERSONALITY):
            SYSTEM_PROMPT =  """You are MARX, a helpful, friendly, and casual AI assistant. 
                        Keep answers brief and easy to understand. Avoid unnecessary fluff. 
                        Let me know if you don't know the answer to something. Don't make things up."""
        else:
            with open(PERSONALITY, 'r') as f:
                SYSTEM_PROMPT=  f.read()
        return(SYSTEM_PROMPT)        
    
    def getName(self):
        return self.personalities[self.index].replace(".txt","")


togglePrompt = ToggleSystemPropmt()

togglePrompt()
print(togglePrompt.getName())
togglePrompt()
print(togglePrompt.getName())
togglePrompt()
print(togglePrompt.getName())
