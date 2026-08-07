## Simulaca Brain

An extensible FastAPI service with a built React dashboard served at `/` from the backend.

### Run locally (full project)

1. Install dashboard dependencies and build the frontend assets:

```bash
cd simulaca_dashboard
npm install
npm run build
cd ..
```

2. Activate the Python environment:

```bash
source simulaca_brain/.venv/bin/activate
```

3. Install backend dependencies if needed:

```bash
uv pip install -r simulaca_brain/requirements.txt
```

4. Start the backend server with uvicorn:

```bash
uv uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

5. Open the dashboard in your browser:

```text
http://127.0.0.1:8000/
```

6. Useful endpoints:

- `http://127.0.0.1:8000/docs` — FastAPI docs
- `http://127.0.0.1:8000/api/v1/health` — health check
- `http://127.0.0.1:8000/api/v1/agents` — agent CRUD
- `http://127.0.0.1:8000/api/v1/world` — world state summary

> If your environment does not support the `uv` launcher, use the standard `pip` and `uvicorn` commands after activating the venv.

### Initial API

- `GET /health` — process liveness
- `POST /agents`, `GET /agents`, `GET /agents/{agent_id}`, `PATCH /agents/{agent_id}`, `DELETE /agents/{agent_id}` — validated agent CRUD

SQLite is selected through `SIMULACA_DATABASE_URL` (default: `sqlite:///./data/simulaca.db`). Repositories and services keep HTTP, domain logic, and persistence separate, so later milestones can add cognition without changing CRUD route contracts.

### Tests

```powershell
pytest
```
