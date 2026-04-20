# AgentCrafter — Claude Reference

Full-stack visual AI workflow builder. Users design LangGraph agent graphs through a drag-and-drop UI; all configuration is stored in PostgreSQL and executed at runtime via LangGraph with PostgreSQL checkpointing.

---

## Repo Layout

```
AgentCrafter/
├── backend_django/          # Django REST API + LangGraph runtime
├── frontend/                # React + Vite + ReactFlow UI
├── docker-compose.yml       # postgres + backend + frontend
├── .vscode/launch.json      # debugpy attach config (port 5678)
└── CLAUDE.md                # this file
```

---

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Agent** | Top-level workflow entity. Has `state_schema`, `entry_node`, `exit_nodes`. Status: `draft / active / archived`. |
| **AgentVersion** | Immutable snapshot of an agent's graph (nodes + edges + state_schema). Versions are forked, not edited in-place. |
| **Node** | A single operation in the graph. Has `type` (functional / llm_call / communication), `subtype`, and `config` (JSONB). |
| **Edge** | Connection between nodes. Either `direct` (unconditional) or `conditional` (routed by `condition_config`). |
| **Run** | One execution of an agent. Tracks status, snapshots, checkpoint thread, error, and HITL metadata. |
| **AgentSession** | Conversation context. Accumulates `conversation_history` across multiple Runs. |

---

## Tech Stack

### Backend
| Library | Version | Role |
|---------|---------|------|
| Django | 4.2 | Web framework (migrations, admin, DRF) |
| Django REST Framework | 3.15 | REST API layer |
| SQLAlchemy | 2.0+ | Runtime ORM (all service-layer DB access) |
| LangGraph | **1.1.6** | Graph execution engine |
| langgraph-checkpoint-postgres | 2.0.21 | PostgresSaver checkpointer |
| psycopg3 | latest | Required by langgraph-checkpoint-postgres |
| Pydantic | 2.x | Schema validation |
| Jinja2 | 3.1.4 | Prompt / config templating |
| RestrictedPython | 7.4 | Sandbox for python_inline nodes |
| Langfuse | 4.0 | LLM observability |
| Uvicorn | 0.29 | ASGI server (SSE streaming) |

> **Two ORM layers**: Django ORM is used **only for migrations and admin**. All service code uses SQLAlchemy sessions.

### Frontend
| Library | Version | Role |
|---------|---------|------|
| React | 18.3 | UI framework |
| Vite | 5.2 | Build tool / dev server |
| React Router | 6.23 | Client-side routing |
| ReactFlow | 11.11 | Graph canvas |
| Zustand | 4.5 | Global state |
| Axios | 1.7 | HTTP client |
| @monaco-editor/react | 4.6 | Code editor (Python, JSON) |
| Lucide React | 0.383 | Icons |
| React Hot Toast | 2.4 | Notifications |
| Tailwind CSS | 3.4 | Utility CSS |

---

## Database

- **Postgres 15**, port **5733** (non-standard, set in docker-compose)
- Credentials: `langgraph / langgraph_secret`, database `ldb`
- Default URL: `postgresql://langgraph:langgraph_secret@localhost:5733/ldb`
- Pool: size=20, max_overflow=40, timeout=30s, recycle=1800s (tunable via `DB_POOL_SIZE` etc.)
- **LangGraph checkpointer** uses a separate psycopg3 connection (autocommit=True)
- Checkpointer tables: `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`

---

## Starting the Services

### Docker (recommended)
```bash
docker-compose up --build
# postgres → 5733, backend → 8000, frontend → 3000, debugpy → 5678
```

### Local backend
```bash
cd backend_django
.venv/bin/python manage.py migrate
sh start-backend.sh
```

### Local frontend
```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev   # → localhost:3000
```

### Debug mode env vars
```
BACKEND_DEBUGPY=true
BACKEND_RELOAD=false          # must be false — reload + debugpy conflict
BACKEND_LOG_LEVEL=debug
BACKEND_DEBUGPY_HOST=0.0.0.0
BACKEND_DEBUGPY_PORT=5678
BACKEND_DEBUGPY_WAIT_FOR_CLIENT=false
BACKEND_DEBUGPY_SUBPROCESS=false
```
VS Code attach config is already correct at `.vscode/launch.json` (remoteRoot `/app`, port 5678).

---

## Django Apps & URL Structure

### Apps
| App | Path | Role |
|-----|------|------|
| agents | `backend_django/agents/` | Agent/node/edge CRUD, import/export |
| runs | `backend_django/runs/` | Run execution, pause, resume, SSE stream |
| sessions | `backend_django/sessions/` | Session CRUD + conversation turns |
| config | `backend_django/config/` | Settings, root URLs, ASGI/WSGI, exception handler |
| db | `backend_django/db/` | SQLAlchemy engine, session factory, PostgresSaver |
| base | `backend_django/base/` | Langfuse client wrapper |
| schemas | `backend_django/schemas/` | Pydantic request/response schemas |

### All API Endpoints
```
GET  /health

# Agents
GET    /api/agents
POST   /api/agents
GET    /api/agents/<id>
PUT    /api/agents/<id>
DELETE /api/agents/<id>
POST   /api/agents/<id>/duplicate
POST   /api/agents/import
GET    /api/agents/<id>/validate

# Versions
GET    /api/agents/<id>/versions
GET    /api/agents/<id>/versions/<vid>
GET    /api/agents/<id>/versions/<vid>/export
POST   /api/agents/<id>/versions/<vid>/fork

# Nodes
GET    /api/node-definitions
POST   /api/agents/<id>/nodes                         # legacy (no version)
POST   /api/agents/<id>/versions/<vid>/nodes          # version-scoped
PUT    /api/nodes/<nid>
DELETE /api/nodes/<nid>

# Edges
POST   /api/agents/<id>/edges                         # legacy
POST   /api/agents/<id>/versions/<vid>/edges          # version-scoped
PUT    /api/edges/<eid>
DELETE /api/edges/<eid>

# Sessions
POST   /api/agents/<id>/versions/<vid>/sessions
GET    /api/agents/<id>/versions/<vid>/sessions/<sid>
POST   /api/agents/<id>/versions/<vid>/sessions/<sid>/run

# Runs
GET    /api/agents/<id>/runs
GET    /api/runs/<id>
POST   /api/runs/<id>/pause
POST   /api/runs/<id>/resume          # body: { "human_response": "..." } for HITL
GET    /api/runs/<id>/stream          # SSE — replays state_snapshots

# Langfuse
GET    /api/langfuse/prompts
```

---

## SQLAlchemy Models (`backend_django/models/`)

### Agent (`agent.py`)
```
id, name, description, status (draft/active/archived)
state_schema (JSONB), entry_node, exit_nodes (JSONB[])
metadata_ (JSONB), created_at, updated_at
```

### AgentVersion (`agent_version.py`)
```
id, agent_id, version_number  [UNIQUE per agent]
entry_node, exit_nodes, state_schema, metadata_
created_from_version_id, created_at
```

### Node (`node.py`)
```
id, agent_id, version_id
name  [UNIQUE per version], type (NodeType), subtype (NodeSubtype)
config (JSONB), position_x, position_y, created_at
```

### Edge (`edge.py`)
```
id, agent_id, version_id
source_node_id, target_node_id
edge_type (direct | conditional), condition_config (JSONB), label, created_at
```

### Run (`run.py`)
```
id, agent_id, version_id, session_id
status (pending | running | success | failed | interrupted)
input_data (JSONB), output_data (JSONB)
conversation_turn (JSONB[]), state_snapshots (JSONB[])
error (Text)
checkpoint_thread_id (UUID)       ← LangGraph resume key
resumed_from_run_id (FK → runs)
pause_requested (Boolean)         ← manual pause flag
interrupt_metadata (JSONB)        ← confidence-check HITL payload
started_at, completed_at
```

### AgentSession (`agent_session.py`)
```
id, agent_id, version_id
conversation_history (JSONB[])    ← [{role, content, timestamp}]
created_at, updated_at
```

---

## Enums (`models/enums.py`)

```python
NodeType:     functional | llm_call | communication
NodeSubtype:  python_inline | api_call | agent_call | chat | llm_agent
              rabbitmq_message | kafka | api
NodeCategory: functional | llm | communication
EdgeType:     direct | conditional
RunStatus:    pending | running | success | failed | interrupted
AgentStatus:  draft | active | archived
AgentCallInputMode:  entire_state | state_key | template
AgentCallOutputMode: merge_state | write_to_key
```

---

## Graph Execution Pipeline

```
RunService.start_run()
  └─ creates Run record, returns immediately

execute_run_background()   ← daemon thread
  └─ GraphRunner.compile_and_run()
       ├─ GraphRuntimeRepository.fetch_for_execution()   # load nodes/edges
       ├─ apply_state_schema_defaults()
       ├─ LangGraphBuilder.compile()
       │    ├─ StateGraph(dict)
       │    ├─ NodeRunnerFactory.build() per node
       │    ├─ _wrap_node()  →  snapshot capture + pause check
       │    ├─ add_edge / add_conditional_edges
       │    └─ workflow.compile(checkpointer=PostgresSaver)
       └─ LangGraphExecutor.execute()
            └─ graph.invoke(state_or_Command, {thread_id: ...})
```

### `_wrap_node()` (`builder.py:142`)
Wraps every node function:
1. Calls `fn(state)` — runs the actual node
2. Captures `state_before` / `state_after` snapshot
3. Persists snapshot to DB immediately (atomic JSONB append — survives crashes)
4. Checks `pause_requested` flag → raises `PauseRequestedError` if set
5. Checks `_error` in result → raises `RuntimeError`

### `LangGraphExecutor.execute()` (`executor.py`)
```python
invoke_input = resume_command if resume_command is not None else dict(input_data)
result = graph.invoke(invoke_input, {"configurable": {"thread_id": thread_id}})
```

---

## Node Types in Detail

### `chat` — Direct LLM call (`nodes/types/llm/chat.py`)
Config keys:
```
provider                  azure_openai | anthropic | ollama
model                     model name (e.g. "ai-agent-4o", "claude-sonnet-4-20250514")
api_key_env_var           env var name holding the key
system_prompt             Jinja2 templatable
user_prompt_template      Jinja2, reference state with {{key}}
temperature               float 0–2
max_tokens                int
output_key                state key written with LLM response
parse_json_response       bool — parse response as JSON dict
use_langfuse_prompt       bool
langfuse_prompt_name      Langfuse prompt ID
confidence_threshold_enabled  bool  ← HITL
confidence_threshold          float 0–1
confidence_key                key in JSON output (default "confidence")
```

### `llm_agent` — LangChain agent (`nodes/types/llm/agent.py`)
Same as `chat` plus:
```
structured_output_enabled   bool
structured_output_schema    JSON Schema string — passed to create_agent(response_format=...)
```
Falls back to `build_chat_llm_node` when provider is not `azure_openai / openai / anthropic`.

### `python_inline` — Sandboxed Python (`nodes/types/functional/`)
```
python_inline.code    string — must define "def run(state): ..."
```
- Runs in isolated child process via `task_runner`
- RestrictedPython + blocked imports + timeout + memory cap

### `agent_call` — Delegate to another agent (`nodes/types/functional/`)
```
target_agent_id / target_agent_name
input_mode      entire_state | state_key | template
input_key       (state_key mode)
input_template  Jinja2 (template mode)
output_mode     merge_state | write_to_key
output_key      (write_to_key mode)
include_run_metadata  bool
```
Max recursion: **8** (`GraphRunner.max_agent_call_depth`)

### `api` / `rabbitmq_message` / `kafka` — Communication nodes
All support Jinja2 payload/body templates and write result to `output_key`.

---

## Edge Routing (`services/runtime/edge_router.py`)

`condition_config` shapes:
```python
# Route by state key value (edge label must equal the value)
{"condition_type": "state_key_equals",
 "state_key_equals": {"key": "status"}}

# Route by Python expression result (must match an edge label)
{"condition_type": "python_expression",
 "python_expression": {"expression": "state['score'] > 0.8"}}

# Route by a key the LLM wrote into state
{"condition_type": "llm_router",
 "llm_router": {"routing_key": "next_step"}}
```

---

## HITL Mechanisms

### Manual Pause (between nodes)
1. `POST /api/runs/<id>/pause` → `Run.pause_requested = True`
2. `_wrap_node()` polls flag after every node completion
3. Raises `PauseRequestedError` → run marked `interrupted`
4. `POST /api/runs/<id>/resume` → new Run, same `checkpoint_thread_id`
5. LangGraph reloads checkpoint; continues from next node

### Confidence-Check HITL (inside LLM node)
Implemented via `_apply_confidence_check()` in `chat.py:31` (imported by `agent.py`).

**Flow:**
1. LLM outputs JSON with a `confidence` field (e.g. `{"answer": "...", "confidence": 0.45}`)
2. `_apply_confidence_check()` extracts `response[confidence_key]`
3. If `confidence < threshold` → `langgraph.types.interrupt(payload)` called
4. LangGraph raises `GraphInterrupt` (`langgraph.errors.GraphInterrupt`)
5. `graph_runner.py` catches it before the generic handler:
   - Extracts `e.interrupts[0].value`
   - Stores in `Run.interrupt_metadata`
   - Marks run `interrupted` (resumable)
6. Frontend (`ChatPage.jsx`) reads `interrupt_metadata`, shows review UI
7. `POST /api/runs/<id>/resume` with `{ "human_response": "..." }`
8. `RunService.resume_run()` builds `Command(resume=human_response)` (`langgraph.types.Command`)
9. Executor calls `graph.invoke(Command(resume=...), config=...)`
10. `interrupt()` returns human value; node uses it as final output

**LangGraph imports used:**
```python
from langgraph.types import interrupt, Command   # used in nodes + run_service
from langgraph.errors import GraphInterrupt      # caught in graph_runner
```

**`Run.interrupt_metadata` shape:**
```json
{
  "interrupt_type": "confidence_check",
  "node_name": "classify_intent",
  "confidence": 0.45,
  "threshold": 0.70,
  "llm_response": { "answer": "...", "confidence": 0.45 }
}
```

> LangGraph re-runs the entire LLM node on resume (the LLM is called twice). If the second call has confidence ≥ threshold it uses that result; if still < threshold, `interrupt()` returns the human value.

---

## State Snapshots

Stored in `Run.state_snapshots` (JSONB array). Appended atomically after every node via SQL:
```sql
UPDATE runs SET state_snapshots = state_snapshots || CAST(:snap AS jsonb) WHERE id = :run_id
```
Shape:
```json
{
  "node_id": "42",
  "node_name": "classify_intent",
  "node_type": "llm_call",
  "node_subtype": "chat",
  "state_before": { ... },
  "state_after":  { ... },
  "timestamp": "2025-04-16T10:23:00.123Z"
}
```
Streamed to frontend via `GET /api/runs/<id>/stream` (SSE).

---

## Services Layer Quick Reference

| Class | File | Key Methods |
|-------|------|-------------|
| `RunService` | `services/run_service.py` | `start_run`, `execute_run_background(…, resume_command)`, `resume_run(run_id, human_response)`, `pause_run`, `get_run`, `list_runs` |
| `GraphRunner` | `services/runtime/graph_runner.py` | `compile_and_run(…, resume_command=None)`, `validate_graph` |
| `LangGraphBuilder` | `graph_runtime/builder.py` | `compile(request)`, `_wrap_node` |
| `LangGraphExecutor` | `graph_runtime/executor.py` | `execute(…, resume_command=None)` |
| `GraphRuntimeRepository` | `graph_runtime/fetcher.py` | `fetch_for_execution`, `create_run`, `mark_run_success/failed/interrupted(…, interrupt_metadata)`, `persist_snapshot`, `get_run_for_resume` |
| `NodeRunnerFactory` | `nodes/factory.py` | `build(node_type, subtype, config, …)` |
| `AgentService` | `services/agent_service.py` | `create_agent`, `get_agent`, `update_agent`, `duplicate_agent` |
| `SessionService` | `services/session_service.py` | `create_session`, `get_session`, `append_conversation_turn` |

---

## Exceptions (`services/exceptions.py`)

```python
ServiceError          # base → HTTP 500
  NotFoundError       # → 404
  ValidationError     # → 400
  ConflictError       # → 409
PauseRequestedError   # internal — caught in compile_and_run, not surfaced as REST error
```

DRF handler in `config/exceptions.py` maps these to HTTP status codes.

---

## Langfuse Tracing

- Configure via: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`
- `LangGraphTraceService` (`graph_runtime/tracing.py`) creates a trace per run
- LLM nodes log via `log_llm_generation()` (`services/runtime/langfuse_tracing.py`)
- `use_langfuse_prompt=True` fetches system prompt from Langfuse at runtime
- Langfuse callback handler passed through `execution_context["langfuse_handler"]`

---

## Frontend Routes & Key Components

```
/                                                          Dashboard.jsx
/agents/:agentId/edit                                      GraphEditor.jsx (latest version)
/agents/:agentId/version/:versionId/edit                   GraphEditor.jsx (specific version)
/agents/:agentId/version/:versionId/session/:sessionId     ChatPage.jsx
```

### Component Map
| File | Role |
|------|------|
| `pages/Dashboard.jsx` | Agent list, create / delete / export / version history |
| `pages/GraphEditor.jsx` | Canvas + right-side config panel + toolbar |
| `pages/ChatPage.jsx` | Chat UI, run status, HITL resume (confidence check) |
| `canvas/NodeTypes.jsx` | ReactFlow custom node renderers (llmNode, functionalNode, communicationNode) |
| `canvas/EdgeTypes.jsx` | ReactFlow custom edge renderers |
| `canvas/NodePalette.jsx` | Draggable node type palette |
| `panels/ConfigPanel.jsx` | LLMNodeConfig, FunctionalNodeConfig, CommunicationNodeConfig, EdgeConfigPanel |
| `panels/StateSchemaEditor.jsx` | Agent state schema key/type/default editor |
| `hooks/useGraphStore.js` | Zustand store |
| `api/client.js` | All axios calls |

### `useGraphStore.js` — What it tracks
```javascript
agent           // current agent object
nodes           // ReactFlow nodes (carry full backend config in .data)
edges           // ReactFlow edges
selectedNode    // currently selected node (drives ConfigPanel)
selectedEdge    // currently selected edge
isDirty         // unsaved changes flag
latestRun       // last Run result
```

### `api/client.js` — All exports
```javascript
// Agents
getAgents, getAgent, createAgent, updateAgent, deleteAgent
duplicateAgent, exportAgent, importAgent, validateAgent

// Node definitions
getNodeDefinitions

// Nodes
createNode(agentId, data, versionId?), updateNode, deleteNode

// Edges
createEdge(agentId, data, versionId?), updateEdge, deleteEdge

// Versions
getVersions, getVersion, forkVersion

// Sessions
createSession, getSession, runInSession

// Runs
getRun, getRuns, pauseRun, resumeRun(runId, data?)

// Langfuse
getLangfusePrompts
```

### Node Type Mapping (frontend ↔ backend)
| Backend `type` | Frontend component type |
|----------------|------------------------|
| `llm_call` | `llmNode` |
| `functional` | `functionalNode` |
| `communication` | `communicationNode` |

### CSS Theme Variables (`src/index.css`)
```css
--bg            #0a0e1a    /* page background */
--surface       #111827    /* panel / card */
--border        #1e293b
--border2       #2d3f5c
--accent        #6366f1    /* indigo — interactive */
--text          #e2e8f0
--text-muted    #64748b
--text-dim      #94a3b8
--success       #10b981
--error         #ef4444
--warning       #f59e0b
--llm           #7c3aed    /* LLM node glow */
--functional    #0ea5e9    /* functional node glow */
```

---

## Migrations

Both the Django ORM model (`runs/models.py`) **and** the SQLAlchemy model (`models/run.py`) must stay in sync. To add a column:
1. Edit `models/run.py` (SQLAlchemy `Column`)
2. Edit `runs/models.py` (Django `Field`)
3. `python manage.py makemigrations runs`
4. Commit the generated file

Current migration chain:
```
runs/0001_initial.py
runs/0002_run_checkpoint_fields.py
runs/0003_run_pause_requested.py
runs/0004_run_interrupt_metadata.py   ← adds interrupt_metadata JSONB
```

---

## Adding a New Node Type (Checklist)

1. `models/enums.py` — add to `NodeSubtype`
2. `services/node_definition.py` — add to `NODE_SUBTYPES_BY_TYPE`, write `_build_default_*_config()`, add `NodeDefinitionSpec`
3. `services/runtime/nodes/types/<category>/` — implement `build_<subtype>_node(config, ...) -> NodeRunner`
4. `services/runtime/nodes/factory.py` — route in `NodeRunnerFactory.build()`
5. `frontend/src/components/panels/ConfigPanel.jsx` — add config section
6. `frontend/src/components/canvas/NodeTypes.jsx` — add renderer if new visual style needed

---

## Adding a New API Endpoint (Checklist)

1. Write view in `agents/views.py`, `runs/views.py`, or `sessions/views.py`
2. Register URL in the app's `urls.py`
3. Add function to `frontend/src/api/client.js`
4. Use in the relevant frontend component

---

## Debugging Tips

- **State snapshots** on `Run.state_snapshots` show node-by-node input/output
- **Run error** is on `Run.error` (text); check for `_error` key set inside node results
- **Checkpoint thread** on `Run.checkpoint_thread_id` — inspect LangGraph checkpoint tables directly in Postgres
- **HITL context** on `Run.interrupt_metadata` — shows which node triggered confidence check and what the LLM returned
- `BACKEND_DEBUGPY=true` + `BACKEND_RELOAD=false` → step-through in VS Code (attach to `localhost:5678`)
- Langfuse dashboard shows per-node LLM traces when `LANGFUSE_*` env vars are configured

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
