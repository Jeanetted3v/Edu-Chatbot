from fastapi import FastAPI, Request, HTTPException
import json
import uvicorn


app = FastAPI()
bot = EducationBot('your_mongodb_uri')

@app.post("/webhook")
async def webhook(message: WhatsAppMessage):
    response = await bot.process_message(message.From, message.Body)
    return {"response": [response]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)