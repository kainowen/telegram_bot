import os
from dotenv import load_dotenv, dotenv_values
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from pathlib import Path

DATABASE_URL = os.getenv('DATABASE_URL')

# RAG Configuration
DOCS_DIRECTORY = str(Path(__file__).resolve().parent.parent / os.getenv('DOCS_DIRECTORY'))
CHROMA_DB_PATH = str(Path(__file__).resolve().parent.parent / os.getenv('CHROMA_DB_PATH'))
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL')
OLLAMA_BASE_URL = os.getenv('Ollama_URL')
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

def build_database():
    """One-time build of the vector database"""
    print("🔨 Building vector database from documents...")

    # Load documents
    loaders = [
        DirectoryLoader(DOCS_DIRECTORY, glob="**/*.pdf", loader_cls=PyPDFLoader),
        DirectoryLoader(DOCS_DIRECTORY, glob="**/*.txt", loader_cls=TextLoader),
        DirectoryLoader(DOCS_DIRECTORY, glob="**/*.md", loader_cls=TextLoader, loader_kwargs={"encoding":"utf-8"})
    ]

    all_documents = []
    for loader in loaders:
        try:
            print(loader)
            docs = loader.load()
            all_documents.extend(docs)
            print(f"  📄 Loaded {len(docs)} documents from {loader.__class__.__name__}")
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
    
    if not all_documents:
        print("❌ No documents found!")
        return False
    
    # Split into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = text_splitter.split_documents(all_documents)
    print(f"📝 Created {len(chunks)} chunks")
    
    # Create embeddings and store
    embeddings = OllamaEmbeddings(
        base_url=OLLAMA_BASE_URL,
        model=EMBEDDING_MODEL
    )
    
    # This creates the persistent database
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DB_PATH
    )
    
    print(f"✅ Vector database saved to {CHROMA_DB_PATH}")
    return True

if __name__ == "__main__":
    build_database()