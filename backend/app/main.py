import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import init_db
import app.models  # Ensure all models are registered with SQLAlchemy metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown procedures."""
    # Startup: Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # Auto-create tables for local development SQLite mode
    if settings.DATABASE_URL.startswith("sqlite"):
        await init_db()
        
    yield
    # Shutdown logic (cleanup connections, workers, etc.) if needed


def create_application() -> FastAPI:
    """Factory function for FastAPI application instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        description="Production-ready Smart Resume Screener API with NLP/AI parsing support.",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # Configure CORS
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Global Exception Handler for unhandled errors
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        if settings.DEBUG:
            import traceback
            traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error occurred."},
        )

    # Register API Routers
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Mount Frontend Dashboard Static Assets & Home Route
    from fastapi.responses import HTMLResponse, Response
    from fastapi.staticfiles import StaticFiles

    frontend_candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend")),
        os.path.abspath("frontend"),
        os.path.abspath("../frontend"),
    ]
    frontend_dir = next((d for d in frontend_candidates if os.path.exists(d)), None)

    if frontend_dir:
        css_dir = os.path.join(frontend_dir, "css")
        js_dir = os.path.join(frontend_dir, "js")

        @app.get("/css/{filename}", include_in_schema=False)
        async def get_css(filename: str):
            filepath = os.path.join(css_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    return Response(content=f.read(), media_type="text/css")
            return Response(status_code=404)

        @app.get("/js/{filename}", include_in_schema=False)
        async def get_js(filename: str):
            filepath = os.path.join(js_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    return Response(content=f.read(), media_type="application/javascript")
            return Response(status_code=404)

        @app.get("/", tags=["Frontend Dashboard"], include_in_schema=False, response_class=HTMLResponse)
        async def serve_dashboard():
            index_path = os.path.join(frontend_dir, "index.html")
            if os.path.exists(index_path):
                with open(index_path, "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            return HTMLResponse(content="<h1>Smart Resume Screener API</h1><p>Visit <a href='/api/v1/docs'>/api/v1/docs</a></p>")

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
