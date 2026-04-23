# Postman Assets

Generated from the Django backend under `/Users/yashrajput/ProjectR/AgentCrafter/backend_django`.

## Files

- `AgentCrafter.postman_collection.json`: importable Postman collection with 33 requests grouped by domain.
- `AgentCrafter.local.postman_environment.json`: importable local environment with base URL and reusable ids.

## Import

1. Import `/Users/yashrajput/ProjectR/AgentCrafter/postman/AgentCrafter.postman_collection.json`.
2. Import `/Users/yashrajput/ProjectR/AgentCrafter/postman/AgentCrafter.local.postman_environment.json`.
3. Select the `AgentCrafter Local` environment.
4. Update `baseUrl` if your backend is not running at `http://localhost:8000`.

The collection includes lightweight test scripts that automatically copy created resource ids into collection variables like `agentId`, `versionId`, `sessionId`, and `runId`.

## API Inventory

Source files analyzed:

- `/Users/yashrajput/ProjectR/AgentCrafter/backend_django/config/urls.py`
- `/Users/yashrajput/ProjectR/AgentCrafter/backend_django/agents/urls.py`
- `/Users/yashrajput/ProjectR/AgentCrafter/backend_django/runs/urls.py`
- `/Users/yashrajput/ProjectR/AgentCrafter/backend_django/sessions/urls.py`
- The corresponding `views.py` and `serializers.py` files for request methods and body shapes.

### Health and Utility

- `GET /health`
- `GET /api/node-definitions`
- `GET /api/langfuse/prompts`

### Agents

- `GET /api/agents`
- `POST /api/agents`
- `POST /api/agents/import`
- `GET /api/agents/{agent_id}`
- `PUT /api/agents/{agent_id}`
- `DELETE /api/agents/{agent_id}`
- `POST /api/agents/{agent_id}/duplicate`

### Versions

- `GET /api/agents/{agent_id}/versions`
- `GET /api/agents/{agent_id}/versions/{version_id}`
- `PATCH /api/agents/{agent_id}/versions/{version_id}`
- `POST /api/agents/{agent_id}/versions/{version_id}/fork`
- `GET /api/agents/{agent_id}/versions/{version_id}/export`

### Nodes

- `POST /api/agents/{agent_id}/nodes`
- `POST /api/agents/{agent_id}/versions/{version_id}/nodes`
- `PUT /api/nodes/{node_id}`
- `DELETE /api/nodes/{node_id}`

### Edges

- `POST /api/agents/{agent_id}/edges`
- `POST /api/agents/{agent_id}/versions/{version_id}/edges`
- `PUT /api/edges/{edge_id}`
- `DELETE /api/edges/{edge_id}`

### Sessions

- `GET /api/agents/{agent_id}/versions/{version_id}/sessions`
- `POST /api/agents/{agent_id}/versions/{version_id}/sessions`
- `GET /api/agents/{agent_id}/versions/{version_id}/sessions/{session_id}`
- `POST /api/agents/{agent_id}/versions/{version_id}/sessions/{session_id}/run`

### Runs

- `GET /api/agents/{agent_id}/validate`
- `GET /api/agents/{agent_id}/runs`
- `GET /api/runs/{run_id}`
- `POST /api/runs/{run_id}/resume`
- `POST /api/runs/{run_id}/pause`
- `GET /api/runs/{run_id}/stream`

## Notes

- The backend does not declare request authentication on these APIViews, so the collection does not include auth headers by default.
- `/api/runs/{run_id}/stream` is a Server-Sent Events endpoint and returns `text/event-stream`.
- `/admin/` exists in Django but is not included here because it is not part of the application API surface.
