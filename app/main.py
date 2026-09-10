from fastapi import FastAPI
from app.api import review

app = FastAPI(title="PR Review Agent")

app.include_router(review.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}