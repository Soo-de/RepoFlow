from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import BASE_DIR
from app.logging_config import setup_logging
from app.routes import generate, status, health


def create_app() -> FastAPI:
    setup_logging()

    application = FastAPI(title="RepoFlow", version="0.1.0")
    application.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    application.include_router(health.router)
    application.include_router(generate.router)
    application.include_router(status.router)

    return application


app = create_app()
