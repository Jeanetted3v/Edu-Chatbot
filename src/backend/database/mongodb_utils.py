from typing import Dict, List, Optional, Any
from datetime import datetime
from .init_mongodb import MongoDB


class MongoDBUtils:
    def __init__(self, mongodb: MongoDB):
        self.mongodb = mongodb

    def save_conversation(
        self,
        customer_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save a conversation message.
        
        Args:
            customer_id: Unique identifier for the customer
            role: 'user' or 'assistant'
            content: The message content
            metadata: Additional information about the message
        
        Returns:
            Inserted document ID
        """
        collection = self.mongodb.get_collection('conversations')
        document = {
            "customer_id": customer_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now(),
            "metadata": metadata or {}
        }
        result = collection.insert_one(document)
        return str(result.inserted_id)

    def get_conversation_history(
        self,
        customer_id: str,
        limit: int = 50,
        start_date: Optional[datetime] = None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history for a customer.
        
        Args:
            customer_id: Unique identifier for the customer
            limit: Maximum number of messages to retrieve
            start_date: Optional start date for filtering messages
            include_metadata: Whether to include metadata in the response
        
        Returns:
            List of conversation messages
        """
        collection = self.mongodb.get_collection('conversations')
        query = {"customer_id": customer_id}
        if start_date:
            query["timestamp"] = {"$gte": start_date}
            
        projection = {'_id': 0} if not include_metadata else None
        
        return list(collection.find(
            query,
            projection,
            sort=[("timestamp", -1)],
            limit=limit
        ))

    def save_feedback(
        self,
        conversation_id: str,
        rating: int,
        comment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save customer feedback about a conversation.
        
        Args:
            conversation_id: ID of the conversation
            rating: Numerical rating (e.g., 1-5)
            comment: Optional feedback text
            metadata: Additional feedback metadata
        
        Returns:
            Inserted feedback document ID
        """
        collection = self.mongodb.get_collection('feedback')
        document = {
            "conversation_id": conversation_id,
            "rating": rating,
            "comment": comment,
            "timestamp": datetime.utcnow(),
            "metadata": metadata or {}
        }
        result = collection.insert_one(document)
        return str(result.inserted_id)

    def update_customer_info(
        self,
        customer_id: str,
        info: Dict[str, Any]
    ) -> None:
        """
        Update or create customer information.
        
        Args:
            customer_id: Unique identifier for the customer
            info: Customer information to update
        """
        collection = self.mongodb.get_collection('customers')
        collection.update_one(
            {"customer_id": customer_id},
            {"$set": {**info, "last_updated": datetime.utcnow()}},
            upsert=True
        )

    def get_customer_info(
        self,
        customer_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve customer information.
        
        Args:
            customer_id: Unique identifier for the customer
        
        Returns:
            Customer information or None if not found
        """
        collection = self.mongodb.get_collection('customers')
        result = collection.find_one({"customer_id": customer_id}, {'_id': 0})
        return result

    def get_recent_conversations(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversations across all customers.
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of conversations to retrieve
        
        Returns:
            List of recent conversations
        """
        collection = self.mongodb.get_collection('conversations')
        start_time = datetime.now() - timedelta(hours=hours)
        
        return list(collection.find(
            {"timestamp": {"$gte": start_time}},
            {'_id': 0},
            sort=[("timestamp", -1)],
            limit=limit
        ))

    def delete_customer_data(
        self,
        customer_id: str
    ) -> Dict[str, int]:
        """
        Delete all data related to a customer.
        
        Args:
            customer_id: Unique identifier for the customer
        
        Returns:
            Dictionary with count of deleted documents from each collection
        """
        results = {}
        
        # Delete conversations
        conv_result = self.mongodb.get_collection('conversations').delete_many(
            {"customer_id": customer_id}
        )
        results['conversations'] = conv_result.deleted_count
        
        # Delete customer info
        cust_result = self.mongodb.get_collection('customers').delete_one(
            {"customer_id": customer_id}
        )
        results['customers'] = 1 if cust_result.deleted_count else 0
        
        return results
    
# Usage example:
# Initialize MongoDB
from init_mongodb import init_mongodb
from mongodb_utils import MongoDBUtils

# Create instances
mongodb = init_mongodb()
db_utils = MongoDBUtils(mongodb)

# Use utility functions
customer_id = "user123"

# Save conversation
message_id = db_utils.save_conversation(
    customer_id=customer_id,
    role="user",
    content="What courses do you offer?",
    metadata={"intent": "course_inquiry"}
)

# Get conversation history
history = db_utils.get_conversation_history(customer_id)

# Update customer info
db_utils.update_customer_info(
    customer_id=customer_id,
    info={
        "name": "John Doe",
        "email": "john@example.com",
        "preferences": {"notifications": True}
    }
)

# Clean up
mongodb.close()