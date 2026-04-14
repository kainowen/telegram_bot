import os
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

DOCS_DIRECTORY = "./docs"
CHROMA_DB_PATH = "./chroma_db"
EMBEDDING_MODEL = "nomic-embed-text"
OLLAMA_BASE_URL = "http://192.168.178.43:11434"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

def build_database():
    """One-time build of the vector database"""
    print("🔨 Building vector database from documents...")
    
    # Load documents
    loaders = [
        DirectoryLoader(DOCS_DIRECTORY, glob="**/*.pdf", loader_cls=PyPDFLoader),
        DirectoryLoader(DOCS_DIRECTORY, glob="**/*.txt", loader_cls=TextLoader),
        DirectoryLoader(DOCS_DIRECTORY, glob="**/*.md", loader_cls=TextLoader),
    ]
    
    all_documents = []
    for loader in loaders:
        try:
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