from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.models.schemas import RootResponse
from app.core.config import settings
from app.api.auth_routes import router as auth_router
from app.core.database import Base, engine

# Initialize Database tables
Base.metadata.create_all(bind=engine)
app = FastAPI(
    title="Northstar AI Knowledge Assistant API",
    description="An API that answers questions using fictional Northstar company documents",
    version="1.0.0",
)

# Configure CORS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(auth_router)

@app.get("/", response_model=RootResponse)
async def root():
    return RootResponse(message="Northstar AI Knowledge Assistant API is running")
