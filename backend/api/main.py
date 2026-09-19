from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.routes.sessions import router as sessions_router
from backend.database.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app(*, initialize_database: bool = True) -> FastAPI:
    application = FastAPI(
        title="Document Intake Assistant",
        lifespan=lifespan if initialize_database else None,
    )
    application.include_router(sessions_router)
    return application


app = create_app()
