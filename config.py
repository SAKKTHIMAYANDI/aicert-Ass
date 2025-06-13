from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    # 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
    # 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
    OPENAI_API_KEY = "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"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Sentence Transformer model
    FAISS_INDEX_PATH = "faiss_index"
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = "fastapi_auth"
    COLLECTION_NAME = "fastapi_auth_coll"