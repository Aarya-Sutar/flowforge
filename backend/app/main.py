"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, dashboard, health, requests, rules, tasks
from app.core.config import settings

app = FastAPI(
    title="FlowForge API",
    description="Intelligent business process automation platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(requests.router)
app.include_router(rules.router)
app.include_router(tasks.router)
app.include_router(dashboard.router)
