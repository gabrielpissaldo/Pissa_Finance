from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db

from app.routes.transactions import router as transactions_router

from app.routes.goals import router as goals_router

from app.routes.dashboard import router as dashboard_router

from app.routes.investments import router as investments_router

from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Pissa Finance",
    lifespan=lifespan
)

app.include_router(transactions_router)
app.include_router(goals_router)
app.include_router(dashboard_router)
app.include_router(investments_router)


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
    
app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend"
) 
