import os
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# ================= CONFIGURATION =================
CHROMA_DB_PATH = "./chroma_db"
OLLAMA_BASE_URL = "http://192.168.178.43:11434"
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "gemma4:e4b-it-bf16"
# =================================================

class DocumentQnA:
    def __init__(self):
        """Load existing vector database (no embedding happens here)"""
        print("🔌 Loading existing vector database...")
        
        # Load the embedding model (needed to convert your question to vectors)
        # But note: This loads the model, NOT re-embeds documents
        self.embeddings = OllamaEmbeddings(
            base_url=OLLAMA_BASE_URL,
            model=EMBEDDING_MODEL
        )
        
        # Load the existing database (like opening an SQLite file)
        self.vector_store = Chroma(
            persist_directory=CHROMA_DB_PATH,
            embedding_function=self.embeddings
        )
        
        # Create retriever (like an index in SQL)
        self.retriever = self.vector_store.as_retriever(
            search_kwargs={"k": 4}
        )
        
        # Load LLM
        self.llm = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=LLM_MODEL,
            temperature=0.3,
        )
        
        # Setup prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a technical assistant. Answer based ONLY on the context below.
            If unsure, say "I couldn't find that in the documentation."
            
            Context:
            {context}"""),
            ("human", "{question}")
        ])
        
        # Build chain
        def format_docs(docs):
            return "\n\n---\n\n".join([d.page_content for d in docs])
        
        self.rag_chain = (
            {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        
        print(f"✅ Ready! Database contains documents")
    
    def query(self, question):
        """Query the database (fast - no embedding of documents)"""
        answer = self.rag_chain.invoke(question)
        return answer

# ================= Usage Example =================
if __name__ == "__main__":
    # Initialize once (loads DB)
    qna = DocumentQnA()
    
    # Interactive query loop
    while True:
        question = input("\n❓ Ask a question (or 'quit'): ").strip()
        if question.lower() == 'quit':
            break
        if question:
            answer = qna.query(question)
            print(f"\n🤖 {answer}")