from hydra import compose, initialize
from main import app


def get_config():
    """Dependency to provide Hydra configuration."""
    with initialize(version_base=None, config_path="./config"):
        cfg = compose(config_name="config.yaml", return_hydra_config=True)
    return cfg


def get_service_container():
    """
    Dependency to get the service container from app state.
    This is imported by all routers to access the service container.
    """
    return app.state.service_container