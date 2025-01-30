from typing import Optional, Dict, Union
from pymongo import MongoClient, ServerApi
from pymongo.database import Database
from pymongo.collection import Collection
from dotenv import load_dotenv
import os
import logging

logger = logging.getLogger(__name__)


class MongoDB:
    _instance = None

    def __new__(cls) -> 'MongoDB':
        """New instance creation method to ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(MongoDB, cls).__new__(cls)
            cls._instance.client = None
            cls._instance.db = None
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self.client: Union[None, MongoClient] = None
            self.db: Union[None, Database] = None
            self._collections_config = {
                'conversations': {
                    'indexes': [
                        [('customer_id', 1), ('timestamp', -1)],
                        [('timestamp', 1)]
                    ]
                },
                'customers': {
                    'indexes': [
                        [('customer_id', 1)],
                        [('email', 1)]
                    ]
                },
                'feedback': {
                    'indexes': [
                        [('conversation_id', 1)],
                        [('rating', 1), ('timestamp', -1)]
                    ]
                }
            }

    def connect(self) -> None:
        """Establish connection to MongoDB and initialize collections."""
        if self.client is None:
            load_dotenv()
            mongodb_uri = os.getenv("MONGODB_URI")
            if not mongodb_uri:
                raise ValueError("MongoDB URI not found in environment variables")
            try:
                self.client = MongoClient(mongodb_uri, server_api=ServerApi('1'))
                self.db = self.client['chatbot_db']
                
                # Initialize collections and indexes
                self._initialize_collections()
                
                # Test connection
                self.client.admin.command('ping')
                logger.info("Successfully connected to MongoDB")
                logger.info(f"Available collections: {self.db.list_collection_names()}")
                
            except Exception as e:
                self.client = None
                self.db = None
                raise ConnectionError(f"Failed to connect to MongoDB: {str(e)}")

    def _initialize_collections(self) -> None:
        """Initialize collections and their indexes."""
        for coll_name, config in self._collections_config.items():
            if coll_name not in self.db.list_collection_names():
                self.db.create_collection(coll_name)
            
            collection = self.db[coll_name]
            existing_indexes = collection.list_indexes()
            existing_index_keys = [list(idx['key'].items()) for idx in existing_indexes]
            
            # Create configured indexes if they don't exist
            for index_spec in config['indexes']:
                if index_spec not in existing_index_keys:
                    collection.create_index(index_spec)

    def get_collection(self, collection_name: str) -> Collection:
        """Get a collection by name, ensuring connection exists."""
        if not self.client:
            self.connect()
        if collection_name not in self._collections_config:
            raise ValueError(f"Unknown collection: {collection_name}")
        return self.db[collection_name]

    def close(self) -> None:
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MongoDB connection closed")

    @property
    def database(self) -> Database:
        """Get the database instance, ensuring connection exists."""
        if not self.client:
            self.connect()
        return self.db


def init_mongodb() -> MongoDB:
    """Initialize and return MongoDB instance."""
    mongodb = MongoDB()
    mongodb.connect()
    return mongodb
