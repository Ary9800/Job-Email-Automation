from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import config, find_jobs, jobs, phase3
from app.services.daily_scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Job Email Automation",
    description="Upload job screenshots, extract details, generate and send application emails",
    version="1.2.0",
    lifespan=lifespan,
)

_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]
if settings.allow_linkedin_cors:
    _origins.extend([
        "https://www.linkedin.com",
        "https://linkedin.com",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.linkedin\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(jobs.router)
app.include_router(find_jobs.router)
app.include_router(phase3.router)


@app.get("/")
async def root():
    return {"message": "Job Email Automation API", "docs": "/docs", "version": "1.2.0"}
