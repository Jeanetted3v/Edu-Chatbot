from typing import Dict, List, Optional

from .intent_classifier import IntentClassifier
from .chat_history_db import ChatHistory, ConversationMemory
from langchain.chains import ConversationalRetrievalChain


class QueryHandler:
    def __init__(
        self,
        vector_store,
        course_data_path: str,
        teacher_data_path: str,
        mongodb_uri: str,
        llm,
        database: str = "education_chatbot"
    ):
        self.vector_store = vector_store
        self.llm = llm
        self.intent_classifier = IntentClassifier(llm)
        self.chat_history = ChatHistory(mongodb_uri, database)
        
        # Load data
        self.course_data = pd.read_csv(course_data_path)
        self.teacher_data = pd.read_csv(teacher_data_path)
        
    def create_conversation_chain(self, customer_id: str):
        """Create a new conversation chain with custom memory for a customer"""
        memory = ConversationMemory(
            chat_history=self.chat_history,
            customer_id=customer_id,
            memory_key="chat_history",
            return_messages=True
        )
        
        return ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.vector_store.as_retriever(),
            memory=memory
        )

    async def handle_query(
        self,
        query: str,
        customer_id: str,
        age: Optional[int] = None,
        course_id: Optional[str] = None,
        teacher_id: Optional[str] = None
    ) -> Dict:
        """
        Enhanced query handling with intent classification
        Returns: Dict containing response and any required information
        """
        # Classify intent
        intent_info = await self.intent_classifier.classify_intent(query)
        
        # Check if we have all required information
        missing_info = []
        for required in intent_info["required_info"]:
            if required == "age" and age is None:
                missing_info.append("age")
            elif required == "course_id" and course_id is None:
                missing_info.append("course_id")
            elif required == "teacher_id" and teacher_id is None:
                missing_info.append("teacher_id")
        
        if missing_info:
            return {
                "response_type": "information_required",
                "missing_info": missing_info,
                "message": f"To better assist you, I need to know your {', '.join(missing_info)}."
            }
        
        # Handle different intents
        if intent_info["intent"] == "course_inquiry":
            courses = self.get_age_appropriate_courses(age)
            return {
                "response_type": "course_list",
                "message": self.format_course_response(courses),
                "courses": courses
            }
            
        elif intent_info["intent"] == "teacher_inquiry":
            teacher_info = self.get_teacher_info(teacher_id)
            return {
                "response_type": "teacher_info",
                "message": self.format_teacher_response(teacher_info),
                "teacher": teacher_info
            }
            
        else:
            # Handle general inquiries using the conversation chain
            conversation_chain = self.create_conversation_chain(customer_id)
            result = await conversation_chain.arun(query)
            return {
                "response_type": "general",
                "message": result
            }

    def get_age_appropriate_courses(self, age: int) -> List[Dict]:
        """Get courses filtered by age"""
        # Implementation remains the same as before
        pass

    def format_course_response(self, courses: List[Dict]) -> str:
        """Format course information into a natural language response"""
        # Implementation remains the same as before
        pass

    def get_teacher_info(self, teacher_id: str) -> Dict:
        """Get detailed teacher information"""
        return self.teacher_data[
            self.teacher_data['teacher_id'] == teacher_id
        ].iloc[0].to_dict()

    def format_teacher_response(self, teacher_info: Dict) -> str:
        """Format teacher information into a natural language response"""
        return f"""
        Let me tell you about {teacher_info['name']}:
        🎓 Qualification: {teacher_info['qualification']}
        👩‍🏫 Specialization: {teacher_info['specialization']}
        ✨ Experience: {teacher_info['experience']} years
        📚 Courses: {teacher_info['courses_taught']}
        """