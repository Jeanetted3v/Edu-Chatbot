from fastapi import Request, FastAPI, HTTPException
from contextlib import asynccontextmanager
from fastapi import WebSocket
import logging
from hydra import initialize, compose
from src.backend.chat.service_container import ServiceContainer

logger = logging.getLogger(__name__)


def get_config():
    """Dependency to provide Hydra configuration."""
    with initialize(version_base=None, config_path="./../../../config"):
        cfg = compose(config_name="config.yaml", return_hydra_config=True)
    return cfg


# def get_service_container(request: Request = None):
#     """
#     Dependency to get the service container from app state.
#     Can be used directly in endpoints or in the startup event.
#     """
#     if request is None:
#         # For use in the startup event
#         from src.backend.api.main import app
#         return app.state.service_container
#     else:
#         # For use in endpoints via dependency injection
#         return request.app.state.service_container
    

async def get_service_container(request: Request) -> ServiceContainer:
    """Dependency to get the service container from app state."""
    if not hasattr(request.app.state, "service_container"):
        # This is important for handling the case where the app is still starting up
        logger.warning("Service container not available yet - app may still be initializing")
        raise HTTPException(
            status_code=503,  # Service Unavailable
            detail="Service is starting up, please try again in a moment"
        )
    return request.app.state.service_container


async def get_websocket_service_container(websocket: WebSocket) -> ServiceContainer:
    """Dependency to get the service container from app state for WebSocket connections."""
    if not hasattr(websocket.app.state, "service_container"):
        logger.warning("Service container not available for WebSocket - app may still be initializing")
        await websocket.close(code=1013)  # 1013 = Try Again Later
        return None
    return websocket.app.state.service_container


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles initialization and cleanup of service container.
    """
    # Startup code
    cfg = get_config()
    service_container = ServiceContainer(cfg)
    await service_container.initialize()
    
    # Store in app state
    app.state.service_container = service_container
    logger.info("Service container initialized")
    
    yield
    
    # Shutdown code
    if hasattr(app.state, "service_container"):
        await app.state.service_container.cleanup()
        logger.info("Service container cleaned up")