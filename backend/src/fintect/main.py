
from fastapi import FastAPI

app = FastAPI(
    title="FINTECT API",
    description="Secure, Governed & Transparent Agentic Banking Platform",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
