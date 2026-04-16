# Agent Crafter

A full-stack **visual AI workflow builder** powered by LangGraph, where you can design, configure, and execute agent graphs through a drag-and-drop interface. All configuration is persisted in PostgreSQL and fetched at runtime.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Frontend (React + ReactFlow)                   │
│  - Visual graph canvas                          │
│  - Node/edge config panels                      │
│  - State schema editor                          │
│  - Run execution view                           │
└──────────────────┬──────────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────────┐
│  Backend (Django + DRF)                         │
│  - Agent / Node / Edge CRUD                     │
│  - GraphRunner: DB → LangGraph compilation      │
│  - Execution engine with state snapshots        │
│  - SSE streaming for live run updates           │
└──────────────────┬──────────────────────────────┘
                   │ SQLAlchemy ORM
┌──────────────────▼──────────────────────────────┐
│  PostgreSQL                                     │
│  - agents, nodes, edges, runs tables            │
│  - JSONB for flexible config storage            │
└─────────────────────────────────────────────────┘
```

## Quick Start

### With Docker Compose

```bash
# 1. Clone and enter directory
cd AgentCrafter

# 2. Set up environment
cp .env.example .env
# Edit .env to add your API keys:
# - AZURE_OPENAI_API_KEY
# - AZURE_OPENAI_ENDPOINT
# - AZURE_OPENAI_API_VERSION
# - ANTHROPIC_API_KEY (optional)
# - LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL (optional, for tracing)
# - LANGFUSE_HOST (legacy fallback, optional)
# - LANGFUSE_PROMPT_MANAGEMENT / PROFILE_ENV / ENV_NAMESPACE (optional, for prompt fetching)

# 3. Start everything
docker-compose up --build

# Frontend → http://localhost:3000
# Backend API → http://localhost:8000
# Debugger → localhost:5678 (when BACKEND_DEBUGPY=true)
# Health check → http://localhost:8000/health
```

### Database Migrations (Required)

Schema changes are managed with Django migrations.

```bash
cd backend_django

# Apply latest migrations
python manage.py migrate

# (Optional) create a new migration
python manage.py makemigrations
```

### Local Development

**Backend:**
```bash
cd backend_django
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Make sure PostgreSQL is running, then:
python manage.py migrate
./start-backend.sh
```

If you prefer not to activate the virtualenv, use the interpreter inside it directly:

```bash
cd backend_django
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate
PYTHON_BIN=.venv/bin/python ./start-backend.sh
```

Avoid installing backend dependencies into a shared global Python environment. Packages such as `browser-use`, `argilla`, `tensorflow`, and older LangChain integrations can create unrelated resolver conflicts even when this project's own environment is healthy.

### Remote Debugging

The backend supports `debugpy` inside Docker.

```bash
# Set these once in .env:
# BACKEND_DEBUGPY=true
# BACKEND_DEBUGPY_WAIT_FOR_CLIENT=true
# BACKEND_DEBUGPY_SUBPROCESS=false
# BACKEND_RELOAD=false
#
# Then run:
docker-compose up --build
```

Attach your debugger to `localhost:5678`.

If you want the app to start immediately and allow later attach, use:

```bash
# In .env:
BACKEND_DEBUGPY_WAIT_FOR_CLIENT=false
```

That means the normal workflow is:
- set the `BACKEND_*` values once in `.env`
- run `docker-compose up --build`

`BACKEND_DEBUGPY_SUBPROCESS=false` prevents `debugpy` from tracing spawned subprocesses such as inline Python task workers. Set it to `true` only if you need to debug those child processes too.

**Frontend:**
```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

## Node Types

### LLM Call Node
Calls an LLM provider with configurable prompts:
- **Providers:** Azure OpenAI, Anthropic, Ollama
- **Config:** model, system prompt, optional Langfuse prompt name, user prompt template (Jinja2 `{{state.key}}`), temperature, max_tokens
- **Output:** writes response to a named state key

Langfuse integration:
- **Tracing:** each run still creates a graph-level Langfuse trace, and each LLM invocation now sends Langfuse callback metadata when Langfuse is configured.
- **Prompt fetching:** if `use_langfuse_prompt` is enabled on an LLM node, the backend fetches the prompt by `langfuse_prompt_name` using `PROFILE_ENV` / `ENV_NAMESPACE` label rules, then falls back to the inline `system_prompt`.

### Functional Node
Three subtypes:
- **Python Inline** — write a `run(state)` function directly in the editor. Inline code executes through a dedicated task-runner package in an isolated child process with timeouts, memory caps, blocked imports, and a small safe helper set.
- **API Call** — HTTP GET/POST with URL/body templates using `{{state.key}}`
- **Data Transform** — map/filter/extract/merge operations on state

## Edge Types

- **Direct** — unconditional connection from one node to the next
- **Conditional** — routes based on:
  - `state_key_equals` — route when a state key equals a value
  - `python_expression` — route based on a Python expression (e.g. `state['score'] > 0.8`)
  - `llm_router` — route based on a key set by an LLM node

## State Schema

The agent-level state is a shared dictionary passed between all nodes. Define keys, types, and defaults in the **State Schema Editor** (toolbar button). Nodes read input keys and write output keys to this shared state.

## API Reference

The Django backend currently exposes REST endpoints under `http://localhost:8000/api/` and a health endpoint at `http://localhost:8000/health`.

Key endpoints:
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents` | List all agents |
| POST | `/api/agents` | Create agent |
| GET | `/api/agents/{id}` | Get agent with graph |
| POST | `/api/agents/{id}/nodes` | Add node |
| POST | `/api/agents/{id}/edges` | Add edge |
| POST | `/api/agents/{id}/run` | Execute agent |
| GET | `/api/agents/{id}/validate` | Validate graph |
| GET | `/api/agents/{id}/export` | Export to JSON |
| POST | `/api/agents/import` | Import from JSON |
| GET | `/api/runs/{id}` | Get run result |
| GET | `/api/runs/{id}/stream` | SSE stream |

Note:
- Edges now reference node IDs (`source_node_id`, `target_node_id`) with database foreign keys.
- For imports, you can provide node `id` values in `nodes[]` and use those IDs in `edges[]`.

## How It Works

1. **Design** — drag nodes from the palette onto the canvas, connect them with edges
2. **Configure** — click any node to open the config panel and set model, prompts, code, etc.
3. **Set Entry/Exit** — click a node and use the Entry/Exit buttons in the config panel
4. **Validate** — click Validate in the toolbar to check for errors
5. **Run** — click Run, paste JSON input, and watch the execution trace

The `GraphRunner` fetches the full agent definition from PostgreSQL, compiles it into a live execution graph, runs it step by step, and captures state snapshots at each node.
