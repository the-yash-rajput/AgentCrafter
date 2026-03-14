from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.session import create_tables
from api import agents, nodes, edges, runs

app = FastAPI(
    title="LangGraph Builder API",
    description="Visual LangGraph workflow builder — configure, store, and run AI agent graphs",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    create_tables()


app.include_router(agents.router, prefix="/api")
app.include_router(nodes.router, prefix="/api")
app.include_router(edges.router, prefix="/api")
app.include_router(runs.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "service": "LangGraph Builder"}
