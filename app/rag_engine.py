import os
import shutil
import logging
import ollama
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Configure Logging
logging.basicConfig(level=logging.INFO)

# Robust Path Handling
BASE_DIR = os.getcwd()
# Try to find data directory
if os.path.exists(os.path.join(BASE_DIR, "data")):
    DATA_ROOT = os.path.join(BASE_DIR, "data")
elif os.path.exists(os.path.join(BASE_DIR, "..", "data")):
    DATA_ROOT = os.path.join(BASE_DIR, "..", "data")
else:
    DATA_ROOT = "data" # Fallback

DATA_RAW_DIR = os.path.join(DATA_ROOT, "raw")
DATA_PROCESSED_DIR = os.path.join(DATA_ROOT, "processed")
FAISS_INDEX_PATH = os.path.join(DATA_ROOT, "processed", "faiss_index")

from langchain_core.embeddings import Embeddings

# Disable httpx logs
logging.getLogger("httpx").setLevel(logging.WARNING)

class OllamaEmbeddings(Embeddings):
    """Custom Embeddings class to use Ollama natively."""
    def __init__(self, model="tinyllama"):
        self.model = model

    def embed_documents(self, texts):
        embeddings = []
        for text in texts:
            # Batching could be added here for efficiency
            resp = ollama.embeddings(model=self.model, prompt=text)
            embeddings.append(resp['embedding'])
        return embeddings

    def embed_query(self, text):
        resp = ollama.embeddings(model=self.model, prompt=text)
        return resp['embedding']

def ingest_documents():
    """
    Ingests documents from data/raw, creates embeddings, and updates the FAISS index.
    Moves processed files to data/processed to avoid re-processing.
    """
    # Ensure dirs exist
    if not os.path.exists(DATA_RAW_DIR):
        try:
            os.makedirs(DATA_RAW_DIR)
        except OSError: 
            pass # Might exist
    if not os.path.exists(DATA_PROCESSED_DIR):
        os.makedirs(DATA_PROCESSED_DIR, exist_ok=True)

    files = [f for f in os.listdir(DATA_RAW_DIR) if os.path.isfile(os.path.join(DATA_RAW_DIR, f))]
    
    if not files:
        logging.info("No new documents to ingest.")
        return

    logging.info(f"Found {len(files)} new documents. Starting ingestion...")
    
    documents = []
    
    # Load PDFs
    for f in files:
        file_path = os.path.join(DATA_RAW_DIR, f)
        try:
            if f.lower().endswith(".pdf"):
                loader = PyPDFLoader(file_path)
                documents.extend(loader.load())
            elif f.lower().endswith(".txt"):
                loader = TextLoader(file_path)
                documents.extend(loader.load())
        except Exception as e:
            logging.error(f"Failed to load {f}: {e}")

    if not documents:
        logging.warning("No valid documents loaded.")
        return

    # Split Text
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    docs = text_splitter.split_documents(documents)
    
    # Embed and Store
    embeddings = OllamaEmbeddings(model="tinyllama")
    
    if os.path.exists(FAISS_INDEX_PATH):
        try:
            db = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
            db.add_documents(docs)
            logging.info("Updated existing FAISS index.")
        except Exception as e:
            logging.error(f"Error loading existing index, creating new one: {e}")
            db = FAISS.from_documents(docs, embeddings)
    else:
        db = FAISS.from_documents(docs, embeddings)
        logging.info("Created new FAISS index.")

    db.save_local(FAISS_INDEX_PATH)
    
    # Move files to processed
    for f in files:
        src = os.path.join(DATA_RAW_DIR, f)
        dst = os.path.join(DATA_PROCESSED_DIR, f)
        try:
            shutil.move(src, dst)
        except Exception as e:
            logging.error(f"Failed to move {f}: {e}")

    logging.info("Ingestion complete.")

def get_relevant_context(query, k=2):
    """
    Retrieves the most relevant context chunks for a given query.
    k=2 for efficiency and speed.
    """
    if not os.path.exists(FAISS_INDEX_PATH):
        return ""

    embeddings = OllamaEmbeddings(model="tinyllama")
    try:
        db = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        docs = db.similarity_search(query, k=k)
        return "\n\n".join([d.page_content for d in docs])
    except Exception as e:
        logging.error(f"Error retrieving context: {e}")
        return ""

if __name__ == "__main__":
    ingest_documents()