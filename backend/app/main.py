from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.evidence import router as evidence_router
from app.api.inquiries import router as inquiries_router
from app.core.config import settings
from app.core.errors import AppError, app_error_handler
from app.infrastructure.database import engine

app = FastAPI(title="Exporbit API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_exception_handler(AppError, app_error_handler)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=jsonable_encoder({"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": {"errors": exc.errors()}, "request_id": request.headers.get("X-Request-ID")}}))


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(status_code=503, content={"error": {"code": "DATABASE_UNAVAILABLE", "message": "Database operation failed", "details": {}, "request_id": request.headers.get("X-Request-ID")}})


@app.get("/health")
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


app.include_router(inquiries_router, prefix="/api/v1")
app.include_router(evidence_router, prefix="/api/v1")

