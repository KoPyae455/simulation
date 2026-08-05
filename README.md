## Simulaca Brain

An extensible FastAPI service. Milestone 1 implements validated agent CRUD only.

### Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000/api/v1`; interactive documentation is at `/docs`.

### Initial API

- `GET /health` — process liveness
- `POST /agents`, `GET /agents`, `GET /agents/{agent_id}`, `PATCH /agents/{agent_id}`, `DELETE /agents/{agent_id}` — validated agent CRUD

SQLite is selected through `SIMULACA_DATABASE_URL` (default: `sqlite:///./data/simulaca.db`). Repositories and services keep HTTP, domain logic, and persistence separate, so later milestones can add cognition without changing CRUD route contracts.

### Tests

```powershell
pytest
```
