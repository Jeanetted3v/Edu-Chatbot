import logging
import uvicorn
from fastapi import Depends, FastAPI

from fastapi.middleware.cors import CORSMiddleware
from src.backend.utils.logging import setup_logging
from src.backend.api.deps import get_config
from src.backend.api import customer_router, staff_router, webhook_router
from src.backend.chat.service_container import ServiceContainer

setup_logging()
logger = logging.getLogger(__name__)
ORIGINS = ["*"]


app = FastAPI(
    title="Agentic Edu Chatbot",
    description="API an agentic chatbot for educational company.",
    version=1.0,
    docs_url="chat/docs",
    openapi_url="/chat/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Service container dependency
def get_service_container():
    return app.state.service_container


@app.on_event("startup")
async def startup_event():
    cfg = get_config()

    service_container = ServiceContainer(cfg)
    await service_container.initialize()
    
    # Store in app state
    app.state.service_container = service_container
    logger.info("Service container initialized")


@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, "service_container"):
        await app.state.service_container.cleanup()
        logger.info("Service container cleaned up")

app.include_router(customer_router.router, prefix="/api", tags=["customer"], dependencies=[Depends(get_config)])
app.include_router(staff_router.router, prefix="/api", tags=["staff"], dependencies=[Depends(get_config)])
app.include_router(webhook_router.router, prefix="/api", tags=["webhooks"], dependencies=[Depends(get_config)])


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


def main() -> None:
    """Main function to run the FastAPI server."""
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()

