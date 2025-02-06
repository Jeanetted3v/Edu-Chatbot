# Edu Chatbot (on-going enhancements)

<div align="center">

</div>

Edu Chatbot is a customer service chatbot, created to help education enrichment businesses to reply to customer inquiries, through channels such as website, What'sApp, WeChat, Telegram, etc. 

## Overview
This chatbot leverages on Retrieval-Augmented Generation (RAG), Natural Language Processing (NLP) techniques to reply to customer inquiries. It stores unstructured data, such as frequently asked questions (FAQ) into vector database and structured data in excel. When a customer makes an inquiry, it first classifies customer intent, before fetching the relevant information such as course information, general FAQs and respond to the customer accordingly.

## Tech Stack
**OpenAI**  
**PydanticAI**  
**Langchain**
**ChromaDB**  
**MongoDB**  
**GoogleDriveAPI**  
**FastAPI**  

## Key Features
**RAG or Long Context**
- In view of LLM able to handle longer context nowadays, this chatbot is set up to use LLM to retreive information if data is within a certain token count. If token count is over a certain number, we'll fall back to use RAG instead. Token count is set as a configurable parameter in config/data_ingest.yaml

**Loading documents from Google Drive**
- Education company can either load data into Google Drive or locally for both structured and unstructured data ingestion.

**Chunking**
- Langchain is used for chunking for the RAG pipeline.

**Embedding & Vector Database**
- ChromaDB is used here mainly due to its popularity in LLM-related projects. I intend to make it modular to fit in other vector databases (on-going enhancements) 

**Agentic RAG**
- PydanticAI is used here for its simplicity and data valiadation feature. It is able to provide a more direct output, such as during intent classification process. 
- I also intend to use agents to upgrade this project to a more flexible rag system (on-going enhancements)
- For other LLM functions, plain vanilla OpenAI API is used for simplicity and flexibility. 

**Saved Chat History**
- All chat histories are saved in MongoDB, which allows for tracing, further analysis and prompt enhancements (on-going enhancements)