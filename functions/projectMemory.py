from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_classic.memory import ConversationSummaryBufferMemory


# ================= GET HISTORY FUNCTION =================

def get_session_history(session_id: str, DATABASE_URL: str,personality):
    print("Starting: get_session_history")
    """
    Creates or retrieves a SQL-based chat history for a specific user.
    This stores raw message history in the database.
    """
    return SQLChatMessageHistory(
        session_id=session_id,
        connection=DATABASE_URL,
        table_name=personality
    )


# ================= CLEAR HISTORY FUNCTION =================

def clear_session_history(session_id: str, DATABASE_URL,personality):
    print("Starting: clear_session_history")
    """Clears conversation history for a specific user from the database."""
    history = get_session_history(session_id, DATABASE_URL,personality=personality)
    history.clear()



# ================= SQL HISTORY SETUP =================

class SQLBackedSummaryMemory:
    """
    A wrapper that combines ConversationSummaryBufferMemory with SQL persistence.
    This gives you the best of both worlds:
    - Summarization to manage context window
    - Persistent storage in SQL database
    """
    
    def __init__(self, session_id: str, DATABASE_URL,personality,llm, max_token_limit=1000):
        print("Initialising: SQLBackedSummaryMemory")
        self.session_id = session_id
        self.llm = llm
        self.max_token_limit = max_token_limit
        self.DATABASE_URL = DATABASE_URL
        self.personality = personality
        
        # Load existing history from SQL
        self.history = get_session_history(session_id, DATABASE_URL,self.personality)
        
        # Create the summary memory with the loaded history
        self.memory = ConversationSummaryBufferMemory(
            llm=llm,
            max_token_limit=max_token_limit,
            return_messages=True,
            chat_memory=self.history  # This links SQL storage to the memory
        )

        self.memory.save_context
    
    def load_memory_variables(self, inputs):
        print("Starting: load_memory_variables")
        """Return the memory variables (the conversation summary + recent history)."""
        return self.memory.load_memory_variables(inputs)
    
    def save_context(self, inputs, outputs):
        print("Starting: save_context")
        """Save the conversation context to both memory and SQL."""
        self.memory.save_context(inputs, outputs)
    
    def clear(self):
        print("Starting: clear")
        """Clear all memory for this session."""
        self.memory.clear()
        clear_session_history(self.session_id, DATABASE_URL=self.DATABASE_URL,personality=self.personality)
    
    @property
    def chat_memory(self):
        print("Starting: chat_memory")
        """Access the underlying SQL chat memory."""
        return self.history
    


    def get_conversation_memory(self, user_memories):
        """Retrieves or creates a SQL-backed memory for a specific user."""
        print("Starting: get_conversation_memory")
        if self.session_id not in user_memories:
            user_memories[self.session_id] = SQLBackedSummaryMemory(
                session_id=self.session_id,
                llm=self.llm,
                max_token_limit=1000,
                DATABASE_URL=self.DATABASE_URL,
                personality=self.personality
            )
        print(user_memories[self.session_ids])
        return user_memories[self.session_id]
