from fastapi import FastAPI

from fintect.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Secure, Governed & Transparent Agentic Banking Platform",
    version="0.1.0",
    debug=settings.debug,
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
