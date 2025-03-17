"""To test run: python -m src.backend.api.main
Interact via SwaggerUi: http://localhost:8000/chat/docs
"""

import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.backend.utils.logging import setup_logging
from src.backend.api.deps import get_config, lifespan
from src.backend.api import customer_router, staff_router, utils_router
from src.backend.chat.service_container import ServiceContainer
from src.backend.api import websocket_router

setup_logging()
logger = logging.getLogger(__name__)
ORIGINS = ["*"]


app = FastAPI(
    title="Agentic Edu Chatbot",
    description="API an agentic chatbot for educational company.",
    version="1.0",
    docs_url="/chat/docs",
    openapi_url="/chat/openapi.json",
    life_span=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customer_router.router, prefix="/customer", tags=["customer"])
app.include_router(staff_router.router, prefix="/staff", tags=["staff"])
app.include_router(utils_router.router, prefix="/utils", tags=["utils"])
app.include_router(websocket_router.router, prefix="/ws", tags=["websocket"])


@app.get("/")
@app.head("/")
async def root():
    """Root endpoint for the FastAPI server."""
    return {
        "message": "Welcome to the Agentic Edu Chatbot API",
        "version": 1.0,
        "docs": "chat/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for the FastAPI server."""
    return {"status": "healthy"}


app.state.startup_complete = False

@app.on_event("startup")
async def startup_event():
    cfg = get_config()
    service_container = ServiceContainer(cfg)
    await service_container.initialize()
    app.state.service_container = service_container
    app.state.startup_complete = True  # Set flag after initialization
    logger.info("Service container initialized")


def main() -> None:
    """Main function to run the FastAPI server."""
    uvicorn.run(
        "src.backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()

