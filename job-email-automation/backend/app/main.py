from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import config, find_jobs, jobs

app = FastAPI(
    title="Job Email Automation",
    description="Upload job screenshots, extract details, generate and send application emails",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(jobs.router)
app.include_router(find_jobs.router)


@app.get("/")
async def root():
    return {"message": "Job Email Automation API", "docs": "/docs"}
