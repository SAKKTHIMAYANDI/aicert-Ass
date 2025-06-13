from database import db
# STEP 1: Create a debug script to understand the current state
# Save this as debug_rag.py

import os
import faiss
import pickle
from pymongo import MongoClient
from config import Config
from bson import ObjectId

def debug_current_state():
    """Step 1: Check what's currently in your system"""
    print("=" * 60)
    print("🔍 DEBUGGING RAG SYSTEM - CURRENT STATE")
    print("=" * 60)
    
    # Check MongoDB connection and documents
    try:
        client = MongoClient(Config.MONGO_URI)
        db = client[Config.DB_NAME]
        documents = db.documents
        
        mongo_count = documents.count_documents({})
        print(f"📄 MongoDB documents count: {mongo_count}")
        
        if mongo_count > 0:
            print("\n📋 Sample MongoDB documents:")
            for i, doc in enumerate(documents.find().limit(3)):
                text_content = doc.get("text") or doc.get("content")
                has_text = bool(text_content and text_content.strip())
                print(f"  {i+1}. ID: {doc['_id']}")
                print(f"     Has text: {has_text}")
                print(f"     Text length: {len(text_content) if text_content else 0}")
                print(f"     Metadata: {doc.get('metadata', {})}")
                if text_content:
                    print(f"     Sample: {text_content[:100]}...")
                print()
        
    except Exception as e:
        print(f"❌ MongoDB Error: {str(e)}")
        return False
    
    # Check FAISS files
    print("🗂️ FAISS Files Status:")
    faiss_index_exists = os.path.exists("models/faiss_index.bin")
    faiss_mapping_exists = os.path.exists("models/faiss_mapping.pkl")
    
    print(f"  - models/faiss_index.bin: {'✅ EXISTS' if faiss_index_exists else '❌ MISSING'}")
    print(f"  - models/faiss_mapping.pkl: {'✅ EXISTS' if faiss_mapping_exists else '❌ MISSING'}")
    
    # Try to load FAISS index
    if faiss_index_exists and faiss_mapping_exists:
        try:
            index = faiss.read_index("models/faiss_index.bin")
            with open("models/faiss_mapping.pkl", "rb") as f:
                mapping = pickle.load(f)
            
            print(f"📊 FAISS Index Status:")
            print(f"  - Vectors count: {index.ntotal}")
            print(f"  - Dimension: {index.d}")
            print(f"  - Mapping entries: {len(mapping)}")
            
            if len(mapping) > 0:
                print(f"  - Sample mapping: {list(mapping.items())[:3]}")
                
        except Exception as e:
            print(f"❌ FAISS Loading Error: {str(e)}")
    
    print("=" * 60)
    return True

# STEP 2: Complete fixed VectorDB class
# Replace your embedding.py with this improved version

import faiss
import numpy as np
import openai
from pymongo import MongoClient
from config import Config
import pickle
import os
from typing import Dict, List
from datetime import datetime
from bson import ObjectId

openai.api_key = Config.OPENAI_API_KEY
EMBEDDING_MODEL = "text-embedding-3-small"

class FixedVectorDB:
    def __init__(self):
        self.dimension = 1536
        self.index = faiss.IndexFlatL2(self.dimension)
        self.id_to_doc = {}
        self.client = MongoClient(Config.MONGO_URI)
        self.db = self.client[Config.DB_NAME]
        self.documents = self.db.documents
        
        # Ensure models directory exists
        if not os.path.exists("models"):
            os.makedirs("models")
            print("📁 Created models directory")
        
        self._load_index()
        
        print(f"[FAISS] Initialized. Total vectors: {self.index.ntotal}")
        print(f"[FAISS] Mapped docs: {len(self.id_to_doc)}")
        
        # Auto-rebuild if empty but MongoDB has documents
        self._auto_rebuild_if_needed()

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding from OpenAI API with error handling"""
        try:
            response = openai.embeddings.create(
                input=text,
                model=EMBEDDING_MODEL
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"❌ Error getting embedding: {str(e)}")
            raise

    def add_document(self, text: str, metadata: Dict) -> str:
        """Add document to both MongoDB and FAISS index"""
        print("📄 Adding document to FAISS and MongoDB")
        
        if not text or not text.strip():
            raise ValueError("Text content cannot be empty")

        # Insert into MongoDB first
        doc_data = {
            "text": text,
            "metadata": metadata,
            "created_at": datetime.now()
        }

        try:
            doc_id = str(self.documents.insert_one(doc_data).inserted_id)
            print(f"✅ Inserted into MongoDB with ID: {doc_id}")
        except Exception as e:
            print(f"❌ MongoDB insertion failed: {str(e)}")
            raise

        # Generate embedding and add to FAISS
        try:
            embedding = self._get_embedding(text)
            embedding = np.array(embedding).astype('float32').reshape(1, -1)

            faiss_id = self.index.ntotal
            self.index.add(embedding)
            self.id_to_doc[faiss_id] = doc_id

            print(f"✅ FAISS ID {faiss_id} added → maps to doc ID {doc_id}")

            # Save immediately after each addition
            self._save_index()
            print("💾 Index and mapping saved to disk")

            return doc_id
            
        except Exception as e:
            # If FAISS addition fails, remove from MongoDB to maintain consistency
            print(f"❌ FAISS addition failed: {str(e)}")
            self.documents.delete_one({"_id": ObjectId(doc_id)})
            raise

    def search(self, query: str, k: int = 5, document_ids: List[str] = None) -> List[Dict]:
        """Search documents with improved debugging and filtering"""
        print(f"🔍 Searching for query: '{query}'")
        print(f"📄 Filter by document_ids: {document_ids}")
        print(f"📊 FAISS index status: {self.index.ntotal} vectors, {len(self.id_to_doc)} mappings")
        
        # Check if index is empty
        if self.index.ntotal == 0:
            print("⚠️ FAISS index is empty! No documents to search.")
            return []
        
        # Validate document_ids if provided
        if document_ids:
            available_docs = set(self.id_to_doc.values())
            requested_docs = set(str(d) for d in document_ids)
            intersection = available_docs.intersection(requested_docs)
            
            print(f"📋 Available in FAISS: {sorted(available_docs)}")
            print(f"📋 Requested: {sorted(requested_docs)}")
            print(f"📋 Intersection: {sorted(intersection)}")
            
            if not intersection:
                print("⚠️ None of the requested documents are in the FAISS index")
                return []

        try:
            # Get query embedding
            query_embedding = self._get_embedding(query)
            query_embedding = np.array(query_embedding).astype('float32').reshape(1, -1)

            # Search FAISS index
            distances, indices = self.index.search(query_embedding, min(k, self.index.ntotal))
            print(f"📏 Distances: {distances[0][:5]}")  # Show first 5
            print(f"🔢 Indices: {indices[0][:5]}")      # Show first 5

            results = []

            for rank, (idx, distance) in enumerate(zip(indices[0], distances[0])):
                if idx == -1:  # No more results
                    continue
                
                if idx not in self.id_to_doc:
                    print(f"⚠️ FAISS index {idx} not found in mapping")
                    continue

                doc_id = self.id_to_doc[idx]
                print(f"→ Rank {rank}: FAISS ID {idx} → MongoDB ID {doc_id}")

                # Filter by document_ids if specified
                if document_ids and doc_id not in [str(d) for d in document_ids]:
                    print(f"  ⛔ Skipped (not in requested document_ids)")
                    continue

                # Fetch from MongoDB
                try:
                    mongo_doc = self.documents.find_one({"_id": ObjectId(doc_id)})
                    if not mongo_doc:
                        print(f"  ⚠️ Document {doc_id} not found in MongoDB")
                        continue

                    text_content = mongo_doc.get("text") or mongo_doc.get("content")
                    if not text_content:
                        print(f"  ⚠️ Document {doc_id} has no text content")
                        continue

                    results.append({
                        "text": text_content,
                        "metadata": mongo_doc.get("metadata", {}),
                        "score": float(distance),
                        "document_id": doc_id
                    })
                    print(f"  ✅ Added to results (score: {distance:.4f})")

                except Exception as e:
                    print(f"  ❌ Error fetching document {doc_id}: {str(e)}")
                    continue

            print(f"✅ Search completed: {len(results)} results found")
            return results

        except Exception as e:
            print(f"❌ Search error: {str(e)}")
            return []

    def _save_index(self):
        """Save FAISS index and mapping to disk"""
        try:
            faiss.write_index(self.index, "models/faiss_index.bin")
            with open("models/faiss_mapping.pkl", "wb") as f:
                pickle.dump(self.id_to_doc, f)
            print("💾 Index and mapping saved successfully")
        except Exception as e:
            print(f"❌ Error saving index: {str(e)}")
            raise

    def _load_index(self):
        """Load FAISS index and mapping from disk"""
        try:
            if os.path.exists("models/faiss_index.bin") and os.path.exists("models/faiss_mapping.pkl"):
                self.index = faiss.read_index("models/faiss_index.bin")
                with open("models/faiss_mapping.pkl", "rb") as f:
                    self.id_to_doc = pickle.load(f)
                print("✅ Loaded FAISS index and mapping from disk")
            else:
                print("ℹ️ No existing FAISS index found — starting fresh")
        except Exception as e:
            print(f"⚠️ Error loading index: {str(e)} — starting fresh")
            self.index = faiss.IndexFlatL2(self.dimension)
            self.id_to_doc = {}

    def _auto_rebuild_if_needed(self):
        """Auto-rebuild FAISS index if it's empty but MongoDB has documents"""
        if self.index.ntotal == 0:
            mongo_count = self.documents.count_documents({})
            if mongo_count > 0:
                print(f"🔄 FAISS index empty but MongoDB has {mongo_count} documents. Auto-rebuilding...")
                self.rebuild_index()

    def rebuild_index(self) -> int:
        """Rebuild FAISS index from all MongoDB documents"""
        print("♻️ Rebuilding FAISS index from MongoDB...")
        
        # Reset index and mapping
        self.index = faiss.IndexFlatL2(self.dimension)
        self.id_to_doc = {}
        
        docs_processed = 0
        docs_failed = 0
        
        try:
            total_docs = self.documents.count_documents({})
            print(f"📄 Found {total_docs} documents in MongoDB")
            
            for doc in self.documents.find():
                try:
                    # Get text content
                    text = doc.get("text") or doc.get("content")
                    if not text or not text.strip():
                        print(f"⚠️ Skipping {doc['_id']} - no text content")
                        docs_failed += 1
                        continue
                    
                    # Generate embedding
                    embedding = self._get_embedding(text)
                    embedding = np.array(embedding).astype('float32').reshape(1, -1)
                    
                    # Add to FAISS
                    faiss_id = self.index.ntotal
                    self.index.add(embedding)
                    self.id_to_doc[faiss_id] = str(doc["_id"])
                    
                    docs_processed += 1
                    if docs_processed % 10 == 0:  # Progress update every 10 docs
                        print(f"📈 Progress: {docs_processed}/{total_docs} documents processed")
                    
                except Exception as e:
                    print(f"❌ Error processing {doc.get('_id', 'unknown')}: {str(e)}")
                    docs_failed += 1
                    continue
            
            # Save the rebuilt index
            self._save_index()
            
            print(f"✅ Rebuild complete!")
            print(f"  📊 Processed: {docs_processed}")
            print(f"  ❌ Failed: {docs_failed}")
            print(f"  🔢 Total vectors: {self.index.ntotal}")
            
            return docs_processed
            
        except Exception as e:
            print(f"❌ Rebuild failed: {str(e)}")
            raise

    def get_stats(self) -> Dict:
        """Get current statistics"""
        mongo_count = self.documents.count_documents({})
        return {
            "faiss_vectors": self.index.ntotal,
            "mapping_entries": len(self.id_to_doc),
            "mongodb_documents": mongo_count,
            "index_dimension": self.index.d
        }

# STEP 3: Test script to verify everything works
def test_complete_system():
    """Test the complete system end-to-end"""
    print("=" * 60)
    print("🧪 TESTING COMPLETE RAG SYSTEM")
    print("=" * 60)
    
    # Initialize fixed VectorDB
    vector_db = FixedVectorDB()
    
    # Show current stats
    stats = vector_db.get_stats()
    print(f"📊 Current Stats: {stats}")
    
    # Test search with a specific document ID from your logs
    test_doc_id = "684acd5357ad72463648c473"  # From your logs
    test_query = "hi"
    
    print(f"\n🔍 Testing search:")
    print(f"  Query: '{test_query}'")
    print(f"  Document ID: {test_doc_id}")
    
    results = vector_db.search(test_query, document_ids=[test_doc_id])
    
    if results:
        print(f"✅ Search successful! Found {len(results)} results")
        for i, result in enumerate(results):
            print(f"  Result {i+1}:")
            print(f"    Score: {result['score']:.4f}")
            print(f"    Text preview: {result['text'][:100]}...")
    else:
        print("❌ No results found")
        
        # Check if document exists in MongoDB
        from bson import ObjectId
        mongo_doc = db.documents.find_one({"_id": ObjectId(test_doc_id)})
        if mongo_doc:
            print(f"  ℹ️ Document exists in MongoDB")
            print(f"  ℹ️ Has text: {bool(mongo_doc.get('text') or mongo_doc.get('content'))}")
        else:
            print(f"  ⚠️ Document not found in MongoDB")

if __name__ == "__main__":
    # Run debug first
    debug_current_state()
    
    # Then test the system
    test_complete_system()