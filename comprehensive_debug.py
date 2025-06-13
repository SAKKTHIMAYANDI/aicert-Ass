# comprehensive_debug.py - Complete debugging and fixing script

import os
import sys
from pymongo import MongoClient
from bson import ObjectId
from config import Config

def debug_mongodb_connection():
    """Debug MongoDB connection and find where your documents actually are"""
    print("=" * 80)
    print("🔍 COMPREHENSIVE MONGODB DEBUG")
    print("=" * 80)
    
    print(f"📝 Config values:")
    print(f"  MONGO_URI: {Config.MONGO_URI}")
    print(f"  DB_NAME: {Config.DB_NAME}")
    print()
    
    try:
        # Connect to MongoDB
        print("🔌 Connecting to MongoDB...")
        client = MongoClient(Config.MONGO_URI)
        
        # Test connection
        client.admin.command('ismaster')
        print("✅ MongoDB connection successful!")
        
        # List all databases
        print("\n📚 Available databases:")
        db_names = client.list_database_names()
        for db_name in db_names:
            print(f"  - {db_name}")
        
        # Check if your configured database exists
        if Config.DB_NAME in db_names:
            print(f"\n✅ Your configured database '{Config.DB_NAME}' exists")
        else:
            print(f"\n⚠️ Your configured database '{Config.DB_NAME}' does not exist!")
            print("Available databases with documents:")
            for db_name in db_names:
                if db_name not in ['admin', 'config', 'local']:
                    db = client[db_name]
                    collections = db.list_collection_names()
                    if collections:
                        print(f"  🗃️ {db_name}: {collections}")
        
        # Check your configured database and collection
        db = client[Config.DB_NAME]
        collections = db.list_collection_names()
        print(f"\n📁 Collections in '{Config.DB_NAME}':")
        for collection_name in collections:
            collection = db[collection_name]
            count = collection.count_documents({})
            print(f"  - {collection_name}: {count} documents")
            
            # Show sample documents if any exist
            if count > 0 and count <= 5:
                print(f"    Sample documents:")
                for doc in collection.find().limit(3):
                    print(f"      ID: {doc.get('_id')}")
                    if 'text' in doc:
                        print(f"      Text: {doc['text'][:50]}...")
                    if 'content' in doc:
                        print(f"      Content: {doc['content'][:50]}...")
                    print()
        
        # Look for the specific document ID from your logs
        target_doc_id = "684acd5357ad72463648c473"
        print(f"\n🎯 Searching for document ID: {target_doc_id}")
        
        found_document = False
        
        # Check all databases and collections for this document
        for db_name in db_names:
            if db_name in ['admin', 'config', 'local']:
                continue
                
            db = client[db_name]
            for collection_name in db.list_collection_names():
                collection = db[collection_name]
                try:
                    doc = collection.find_one({"_id": ObjectId(target_doc_id)})
                    if doc:
                        print(f"✅ FOUND in database '{db_name}', collection '{collection_name}'!")
                        print(f"   Document details:")
                        print(f"   - ID: {doc['_id']}")
                        print(f"   - Has 'text': {'text' in doc}")
                        print(f"   - Has 'content': {'content' in doc}")
                        print(f"   - Created: {doc.get('created_at', 'N/A')}")
                        print(f"   - Metadata: {doc.get('metadata', {})}")
                        print(f"   - Uploaded by: {doc.get('uploaded_by', 'N/A')}")
                        
                        text_content = doc.get('text') or doc.get('content')
                        if text_content:
                            print(f"   - Text length: {len(text_content)}")
                            print(f"   - Text preview: {text_content[:100]}...")
                        
                        found_document = True
                        
                        # This is probably where your documents are!
                        if db_name != Config.DB_NAME or collection_name != 'documents':
                            print(f"\n⚠️ CONFIGURATION MISMATCH DETECTED!")
                            print(f"Your document is in: {db_name}.{collection_name}")
                            print(f"Your config points to: {Config.DB_NAME}.documents")
                        
                except Exception as e:
                    continue
        
        if not found_document:
            print(f"❌ Document {target_doc_id} not found in any database/collection")
            print("This suggests the document might have been deleted or the ID is incorrect")
        
        return client
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {str(e)}")
        return None

def check_config_file():
    """Check if config file has correct values"""
    print("\n" + "=" * 80)
    print("⚙️ CHECKING CONFIG FILE")
    print("=" * 80)
    
    try:
        import config
        print("✅ Config file imported successfully")
        
        # Check if Config class exists and has required attributes
        if hasattr(config, 'Config'):
            config_class = config.Config
            required_attrs = ['MONGO_URI', 'DB_NAME', 'OPENAI_API_KEY']
            
            for attr in required_attrs:
                if hasattr(config_class, attr):
                    value = getattr(config_class, attr)
                    if attr == 'OPENAI_API_KEY':
                        # Don't print the full API key
                        print(f"  ✅ {attr}: {'sk-...' + value[-10:] if value and value.startswith('sk-') else 'SET' if value else 'MISSING'}")
                    else:
                        print(f"  ✅ {attr}: {value}")
                else:
                    print(f"  ❌ {attr}: MISSING")
        else:
            print("❌ Config class not found in config.py")
            
    except ImportError as e:
        print(f"❌ Cannot import config: {str(e)}")
    except Exception as e:
        print(f"❌ Config error: {str(e)}")

def suggest_fixes(client):
    """Suggest fixes based on what we found"""
    print("\n" + "=" * 80)
    print("🔧 SUGGESTED FIXES")
    print("=" * 80)
    
    if not client:
        print("1. ❌ Fix MongoDB connection first")
        print("   - Check your MONGO_URI in config.py")
        print("   - Ensure MongoDB is running")
        print("   - Check network connectivity")
        return
    
    # Check if documents exist but in wrong place
    target_doc_id = "684acd5357ad72463648c473"
    
    # Option 1: Update config to point to correct database
    print("📋 OPTION 1: Update your config.py")
    print("If your documents are in a different database/collection:")
    print("  1. Update Config.DB_NAME in config.py")
    print("  2. Update collection name if it's not 'documents'")
    print()
    
    # Option 2: Re-upload documents
    print("📋 OPTION 2: Re-upload your documents")
    print("If no documents exist or they're corrupted:")
    print("  1. Use your document upload endpoint to add documents")
    print("  2. Make sure the upload process calls vector_db.add_document()")
    print()
    
    # Option 3: Manual test upload
    print("📋 OPTION 3: Test manual document upload")
    print("Create a test document to verify the system works:")
    
    test_code = '''
# test_upload.py
from embedding import FixedVectorDB
from rag import RAGSystem

# Initialize system
vector_db = FixedVectorDB()
rag_system = RAGSystem(vector_db)

# Test document
test_text = "This is a test document about artificial intelligence and machine learning."
test_metadata = {"title": "Test Document", "type": "test"}

# Add document
doc_id = vector_db.add_document(test_text, test_metadata)
print(f"Added test document with ID: {doc_id}")

# Test search
results = vector_db.search("artificial intelligence", document_ids=[doc_id])
print(f"Search results: {len(results)} found")

if results:
    print("✅ System is working!")
else:
    print("❌ System still not working")
'''
    
    print("Save this as test_upload.py and run it:")
    print(test_code)

def main():
    """Run complete debugging process"""
    print("🚀 Starting comprehensive RAG system debugging...")
    
    # Step 1: Check config
    check_config_file()
    
    # Step 2: Debug MongoDB
    client = debug_mongodb_connection()
    
    # Step 3: Suggest fixes
    suggest_fixes(client)
    
    print("\n" + "=" * 80)
    print("✅ DEBUGGING COMPLETE")
    print("=" * 80)
    print("Next steps:")
    print("1. Fix any configuration issues identified above")
    print("2. Re-upload documents if needed")
    print("3. Test with the manual upload script")
    print("4. Run your main application")

if __name__ == "__main__":
    main()