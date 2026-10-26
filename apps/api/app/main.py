from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import Base, engine
from .routers import auth, fields, recommend, satellite


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist. (Real deploys use Alembic migrations instead.)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Agrismart 2.0 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(fields.router)
app.include_router(recommend.router)
app.include_router(satellite.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
