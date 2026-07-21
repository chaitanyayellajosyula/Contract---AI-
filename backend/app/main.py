from fastapi import FastAPI

from app.api import auth_router, dashboard_router, jobs_router, recruiters_router, vendors_router
from app.core.database import Base, engine
from app.models import user, team

app = FastAPI(
    title="Contract Hunter AI API",
    description="Application foundation for Contract Hunter AI.",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(jobs_router)
app.include_router(vendors_router)
app.include_router(recruiters_router)

Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
