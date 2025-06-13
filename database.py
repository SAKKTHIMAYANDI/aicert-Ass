# from pymongo import MongoClient
# from pymongo.errors import ConnectionFailure
# from config import Config

# MONGO_URI = "mongodb://localhost:27017"
# DB_NAME = "fastapi_auth"
# COLLECTION_NAME = "fastapi_auth_coll"

# try:
#     client = MongoClient(MONGO_URI)
#     client.admin.command('ping')
#     db = client[DB_NAME]
#     documents = client[COLLECTION_NAME]
#     print("Connected to MongoDB successfully!")
# except ConnectionFailure as e:
#     print(f"Could not connect to MongoDB: {e}")
#     raise


from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from config import Config

class Database:
    def __init__(self):
        try:
            self.client = MongoClient(Config.MONGO_URI)
            self.client.admin.command('ping')
            self.db = self.client[Config.DB_NAME]
            self.users = self.db["users"]  # Add this line
            self.documents = self.db[Config.COLLECTION_NAME]
            print("Connected to MongoDB successfully!")
        except ConnectionFailure as e:
            print(f"Could not connect to MongoDB: {e}")
            raise

    def store_document(self, document_data):
        return self.documents.insert_one(document_data)

    def get_documents(self):
        return list(self.documents.find({}, {'_id': 0}))

    # Add user-related methods
    def get_user(self, username: str):
        return self.users.find_one({"username": username})

    def create_user(self, user_data: dict):
        return self.users.insert_one(user_data)

db = Database()