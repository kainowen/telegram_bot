import os
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from pathlib import Path



class DocumentQnA:
    """Handles Retrieval-Augmented Generation (RAG) for querying local documents."""
    
    def __init__(self,CHROMA_DB_PATH,OLLAMA_BASE_URL,EMBEDDING_MODEL,TARGET_MODEL):
        print("Initialising DocumentQnA...")
        self.is_available = False
        self.retriever = None
        self.rag_chain = None
        self.OLLAMA_BASE_URL = OLLAMA_BASE_URL
        self.EMBEDDING_MODEL = EMBEDDING_MODEL
        self.TARGET_MODEL = TARGET_MODEL
        self.CHROMA_DB_PATH = str(Path(__file__).resolve().parent.parent / CHROMA_DB_PATH)
        
        if not os.path.exists(self.CHROMA_DB_PATH):
            print("⚠️ RAG not available: No vector database found.")
            return

        try:
            embeddings = OllamaEmbeddings(
                base_url=OLLAMA_BASE_URL,
                model=EMBEDDING_MODEL
            )
            
            vector_store = Chroma(
                persist_directory=self.CHROMA_DB_PATH,
                embedding_function=embeddings
            )
            
            self.retriever = vector_store.as_retriever(search_kwargs={"k": 4})
            self.is_available = True
            print("✅ RAG system loaded!")
        except Exception as e:
            print(f"⚠️ RAG initialization failed: {e}")
    
    def query(self, question: str,SYSTEM_PROMPT) -> str:
        """Query the document database with a question."""
        print("Running Query")
        if not self.is_available:
            return "📚 Document Q&A is not available."
        
        try:
            # For RAG, we'll use a simple prompt without memory
            llm = ChatOllama(
                base_url=str(self.OLLAMA_BASE_URL),
                model=str(self.TARGET_MODEL),
                temperature=0.3,
            )

            docs = self.retriever.invoke(question)
            context = "\n\n---\n\n".join([doc.page_content for doc in docs])

            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""{SYSTEM_PROMPT}"

                Context: {context}"""),
                ("human", "{question}")
            ])

            chain = prompt | llm | StrOutputParser()

            return chain.invoke({"context": context, "question": question})
            
        except Exception as e:
            return f"❌ RAG query failed: {str(e)}"