import os
import json
from typing import Sequence
from langchain_ollama import ChatOllama
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser

import data.api_key

# ================= Custom File-Based Persistence =================
class FileChatMessageHistory(BaseChatMessageHistory):
    """Persistent chat history using JSON files. [citation:5]"""

    def __init__(self, session_id: str, storage_path: str = "./chat_histories"):
        self.session_id = session_id
        self.storage_path = storage_path
        self.file_path = os.path.join(storage_path, f"{session_id}.json")
        os.makedirs(storage_path, exist_ok=True)

    @property
    def messages(self) -> list[BaseMessage]:
        """Load messages from file."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return messages_from_dict(data)
        except FileNotFoundError:
            return []

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        """Add messages and persist to file."""
        all_messages = list(self.messages)
        all_messages.extend(messages)

        serialized = [message_to_dict(msg) for msg in all_messages]
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(serialized, f, ensure_ascii=False, indent=2)

    def clear(self) -> None:
        """Clear all messages."""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump([], f)

# ================= Bot Configuration =================
TELEGRAM_BOT_TOKEN = data.api_key.api_key
OLLAMA_BASE_URL = "http://192.168.178.43:11434"
OLLAMA_MODEL = "llama3.2"

# System prompt
SYSTEM_PROMPT = """You are a helpful, friendly AI assistant. 
You remember previous conversations with each user and use that context.
Keep responses concise and natural."""

# Session storage
session_histories = {}

def get_session_history(session_id: str) -> FileChatMessageHistory:
    """Get or create persistent history for a user."""
    if session_id not in session_histories:
        session_histories[session_id] = FileChatMessageHistory(session_id)
    return session_histories[session_id]

# Create Ollama chat model [citation:1][citation:4]
llm = ChatOllama(
    base_url=OLLAMA_BASE_URL,
    model=OLLAMA_MODEL,
    temperature=0.7,
)

# Create prompt with history placeholder
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}")
])

# Build chain
chain = prompt | llm | StrOutputParser()

# Wrap with message history [citation:3][citation:9]
chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

# Usage example
if __name__ == "__main__":
    user_id = "telegram_user_123"
    config = {"configurable": {"session_id": user_id}}

    response = chain_with_history.invoke(
        {"input": "My name is Alex"},
        config=config
    )
    print(response)

    # This will remember "Alex" even after restart
    response = chain_with_history.invoke(
        {"input": "What's my name?"},
        config=config
    )
    print(response)