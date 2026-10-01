from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator


def setup_observability(app: FastAPI) -> None:
    @app.get("/health", tags=["Observability"])
    async def health_check():
        return {"status": "ok"}

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
