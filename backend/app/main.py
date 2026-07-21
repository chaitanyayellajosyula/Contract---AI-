from fastapi import FastAPI

app = FastAPI(
    title="Contract Hunter AI API",
    description="Backend foundation for Contract Hunter AI.",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
