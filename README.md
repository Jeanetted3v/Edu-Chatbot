# Edu Chatbot 

<div align="center">

</div>

Edu Chatbot is a customer service chatbot, created to help education enrichment businesses to answer customer inquiries,through channels such as website, What'sApp, WeChat, Telegram, etc. 

## Overview
This chatbot leverages on Retrieval-Augmented Generation (RAG), Natural Language Processing (NLP) techniques to answer customer inquiries. It stores unstructured data, such as frequently asked questions (FAQ) provided by education companies into vector store and structured data in excel. When a customer makes and inquiry, it first classifies customer intent, before fetching the relevant information such as course information, general FAQs and answers the customer accordingly.

## Tech Stack
**PydanticAI**  
**ChromaDB**  
**MongoDB**  
**OpenAI**  
**GoogleDriveAPI**  
**FastAPI**  

## Key Features
**RAG or Long Context**
- In view of LLM able to handle longer context nowadays, this chatbot is set up to use LLM to retreive information if data is within a certain token count. If token count is over a certain number, we'll fall back to use RAG instead. Token count is set as a configurable parameter. 

**Loading documents from Google Drive**
- Education company can either load data into Google Drive or locally for both structured and unstructured data ingestion.

**Agentic RAG**
- PydanticAI is used here as it is has the data validation feature. I find it helpful when asked to provide a more direct output, such as intent classification. 

**Saved Chat History**
- All chat histories are saved in MongoDB, which allows for tracing and further analysis 

