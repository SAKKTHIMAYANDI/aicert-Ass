from embeddings import VectorDB
from rag import RAGSystem

def test_search():
    print("🧪 Testing the fixed search...")
    
    # Initialize
    vector_db = VectorDB()
    rag_system = RAGSystem(vector_db)
    
    # Your test parameters
    test_doc_id = "684accc9a3383b1ff16a5b24"
    test_query = "hii"
    
    print(f"Testing with document: {test_doc_id}")
    print(f"Query: '{test_query}'")
    
    # Test search
    results = rag_system.search_documents(test_query, k=5, document_ids=[test_doc_id])
    
    if results:
        print(f"✅ SUCCESS! Found {len(results)} results")
        for i, result in enumerate(results):
            print(f"  Result {i+1}:")
            print(f"    Score: {result['score']:.4f}")
            print(f"    Text preview: {result['text'][:100]}...")
    else:
        print("❌ Still no results found")
        
        # Debug: Check if document exists in FAISS
        stats = vector_db.get_stats()
        print(f"Debug info: {stats}")
        print(f"Available docs: {list(vector_db.id_to_doc.values())}")

if __name__ == "__main__":
    test_search()