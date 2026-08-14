# Simulaca Brain

**Simulaca** is an experimental, AI-powered artificial-life simulation.

The long-term goal is a small virtual world containing autonomous NPC
agents whose behavior can evolve through:

- internal needs (hunger, thirst, fatigue, safety, comfort, social)
- perception of the world around them
- episodic memory and memory recall
- goal generation
- structured planning (rule-based **and** LLM-powered)
- reflection, learning, and — later — reinforcement learning

This is an **experimental research / engineering project**, not a finished
AGI system. The LLM is *one component of cognition*, not the entire agent.

The project is split in two parts, both in this repository:

| Directory | Purpose |
|-----------|---------|
| `simulaca_brain/` | Python/FastAPI backend ("the brain") + SQLite persistence |
| `simulaca_dashboard/` | React + Vite developer dashboard (built assets served by the backend) |

---

## Quick Start — Returning to the Project

Run these three things and you are back in business. Details follow in
[Section 8](#8-daily-startup-guide--returning-to-the-project).

```bash
# Terminal 1 — Ollama (skip if already running)
ollama serve

# Terminal 2 — Simulaca backend
cd ~/Git/simulaca/simulaca_brain
source .venv/bin/activate
SIMULACA_PLANNER_TYPE=llm SIMULACA_LLM_MODEL=llama3.2:latest uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

- Dashboard → **http://127.0.0.1:8000/**
- API docs → **http://127.0.0.1:8000/docs**
- Health → **http://127.0.0.1:8000/api/v1/health**

> The default planner is **rule-based** (`SIMULACA_PLANNER_TYPE=rules`).
> Add `SIMULACA_PLANNER_TYPE=llm` as shown above to enable the LLM brain
> (requires Ollama + `llama3.2:latest`).

---

## 1. Project Introduction

Simulaca simulates autonomous agents living in a small world. Each agent:

1. **Has needs** (`AgentNeeds`, 0–100): hunger, thirst, fatigue, safety, comfort, social.
2. **Perceives** its location, nearby locations and nearby entities.
3. **Remembers** episodic events and can recall goal-relevant memories.
4. **Chooses a goal** from its needs (e.g. thirst > 80 → goal `drink`).
5. **Plans** how to satisfy the goal — either deterministically
   (`RuleBasedPlanner`) or with a small local LLM (`LLMPlanner` → Ollama).
6. **Executes** its plan through the simulation tick loop — one validated
   step per tick — and the world/needs change as a consequence.

The simulation ticks on a virtual clock (`SimulationClock`, 1 minute per
tick by default). Each tick advances needs, asks each agent for a decision
(reused until its plan completes), executes one plan step, and persists
the result.

Agent decisions, plans, LLM latency and fallback status are recorded in an
in-memory `BrainStateStore` and exposed through the Brain API so they can
be inspected (see [Section 13](#13-api-reference)).

---

## 2. Current Status

| Version | Milestone | Status |
|---------|-----------|--------|
| V0.1 | Foundation (FastAPI + models + config) | Complete |
| V0.2 | Living Agent (needs tick / state machine) | Complete |
| V0.3 | Episodic Memory | Complete |
| V0.4 | Memory Recall | Complete |
| V0.5 | World State & Perception | Complete |
| V0.6 | Goal-Oriented Planner (`RuleBasedPlanner`, `ActionPlan`, validator, executor) | Complete |
| V0.7 | LLM Cognitive Planner (Ollama provider, brain pipeline, Brain API) | In Progress |
| V0.8 | Reflection | Planned |
| V0.9 | Long-Term Memory & RL | Planned |
| V1.x | Multi-agent interaction, economy, relationships, learning | Planned |

### What "V0.7 In Progress" means today

Implemented and working in the repository:

- Ollama LLM provider (`app/core/llm/ollama.py`, `service.py`) — sends a
  real `/api/generate` request and returns generated text.
- LLM configuration (`SIMULACA_LLM_*`, `SIMULACA_PLANNER_TYPE`,
  `SIMULACA_LLM_FALLBACK_TO_RULES`).
- LLM planner pipeline: `DecisionContext` → `PromptBuilder` → LLM →
  JSON parsing (`llm_response_parser.py`) → Pydantic `ActionPlan` →
  `PlanValidator` → one-step-per-tick `PlanExecutor`.
- `BrainService` orchestration wired into `SimulationService` (the LLM
  proposes an `ActionPlan`; the validator/executor apply the changes).
- Brain API: `GET /api/v1/brain/status`,
  `GET /api/v1/agents/{id}/decision`, `GET /api/v1/agents/{id}/plan`.

Still missing before V0.7 can be marked **Complete**:

- A dedicated `BrainPanel` in the dashboard (the backend Brain endpoints
  exist; the frontend does not render them yet).
- Committed unit tests that exercise the LLM planner with a
  `FakeLLMProvider` (invalid JSON, unknown actions, unknown targets,
  timeout, fallback). The planner code exists; test coverage does not yet.
- A verified end-to-end run of the LLM pipeline against a live Ollama
  server through the full simulation loop.

The planner runs in **rule-based mode by default** so the whole system is
fully usable without Ollama today.
---

## 3. Current Architecture

```
                       World (locations, entities, water, food)
                                   ↓
                           Simulation Engine (clock + tick loop)
                                   ↓
                              Agent State (needs 0–100)
                                   ↓
                                   Needs
                                   ↓
                                Perception
                                   ↓
                              Memory Recall
                                   ↓
                            Decision Context
                                   ↓
                    Planner (CompositePlanner routes by config)
                     ├── RuleBasedPlanner (deterministic)
                     └── LLMPlanner ──► Ollama (llama3.2:latest)
                                   ↓
                              Structured ActionPlan
                                   ↓
                      PlanValidator (actions + targets + schema)
                                   ↓
                      PlanExecutor — one step per tick
                                   ↓
                           World State + Agent Needs
```

Two rules are load-bearing in this architecture:

1. **The LLM does NOT directly modify the world.** It receives a
   `DecisionContext` snapshot and returns a structured `ActionPlan` (JSON).
2. **Only the `PlanValidator` and `PlanExecutor` change state.** Invalid
   JSON, unknown actions, and invented targets are rejected before anything
   executes.

### Cognition pipeline (one agent, one tick)

```
DecisionContext
      ↓
PromptBuilder (bounded context; prompts and chain-of-thought never exposed)
      ↓
Ollama  (or FakeLLMProvider in tests)
      ↓
LLM response text
      ↓
JSON parsing            (llm_response_parser.py)
      ↓
Pydantic validation     (ActionPlan / ActionPlanStep)
      ↓
PlanValidator           (registered actions, real targets)
      ↓
PlanExecutor            (mutates needs / location)
```

A multi-step plan is **reused across ticks** — the `BrainStateStore`
tracks each agent's step cursor, so `[move → river, drink → river]`
executes `move` on tick 1 and `drink` on tick 2.

---

## 4. Repository Structure

```
simulaca/
├── README.md                     ← this file
├── data/                         ← SQLite database files (gitignored)
├── simulaca_brain/               ← Python/FastAPI backend
│   ├── app/
│   │   ├── main.py               ← application factory (create_app)
│   │   ├── api/                  ← FastAPI routers & wiring
│   │   │   ├── router.py         ← aggregates all routers
│   │   │   ├── dependencies.py   ← service/repository wiring (DI graph)
│   │   │   ├── health.py         ← GET /health
│   │   │   ├── agents.py         ← agent CRUD, perception, context
│   │   │   ├── simulation.py     ← step/start/stop
│   │   │   ├── logs.py           ← decision logs
│   │   │   ├── memories.py       ← memory CRUD + recall
│   │   │   ├── world.py          ← world summary/locations/entities
│   │   │   └── brain.py          ← brain/status, decision, plan
│   │   ├── core/                 ← config, LLM, events, exceptions, schemas
│   │   │   ├── config.py         ← typed Settings (SIMULACA_* env vars)
│   │   │   └── llm/              ← provider port + Ollama + Fake + factory
│   │   └── modules/
│   │       ├── agent/            ← agent models, state, repository, logs
│   │       ├── cognition/        ← the brain (V0.6 + V0.7)
│   │       ├── memory/           ← episodic memory + recall service
│   │       ├── simulation/       ← SimulationService tick loop/auto-run
│   │       └── world/            ← locations, entities, clock, perception
│   ├── tests/                    ← pytest suite (offline, no Ollama needed)
│   ├── data/                     ← local SQLite (created at runtime)
│   ├── requirements.txt
│   └── master_prompt.md          ← (currently empty, reserved)
└── simulaca_dashboard/           ← React 19 + Vite + TypeScript + Tailwind
    ├── src/
    │   ├── components/           ← AgentDetail, MemoryPanel, RecallPanel, …
    │   ├── hooks/                ← data-fetching hooks
    │   ├── services/             ← API clients
    │   ├── types/api.ts          ← shared API types
    │   └── App.tsx               ← layout
    ├── dist/                     ← built assets served at “/”
    ├── package.json
    └── vite.config.ts
```

### Important modules

- **`app/modules/simulation/service.py`** — the tick loop: advances needs,
  runs either the legacy inline rule pipeline or (when a `BrainService` is
  injected) the cognition pipeline, persists agents, writes decision logs
  and memories.
- **`app/modules/cognition/planner_service.py`** — `CompositePlanner`
  selects the planner from `SIMULACA_PLANNER_TYPE` and implements the
  `SIMULACA_LLM_FALLBACK_TO_RULES` fallback.
- **`app/modules/cognition/brain_service.py`** — orchestrates
  `ContextBuilder → CompositePlanner → PlanExecutor → BrainStateStore`
  for exactly one validated step per tick.
- **`app/core/llm/`** — `base.py` (provider protocol), `ollama.py`
  (real `/api/generate` client), `fake.py` (`FakeLLMProvider` for
  offline tests), `service.py` (`create_llm_provider()` factory).
- **`app/api/dependencies.py`** — the dependency-injection graph that
  builds repositories, services, the `CompositePlanner`, and the
  `BrainService`.
---

## 5. Requirements

### Backend (Python 3.11+)

| Package | Version (from `requirements.txt`) |
|---------|-----------------------------------|
| fastapi | `>=0.141` |
| pydantic | `>=2.13` |
| pydantic-settings | `>=2.14` |
| uvicorn[standard] | `>=0.30` |
| httpx | `>=0.28` |
| pytest | `>=9.1` (dev/test) |

A virtual environment is provided at `simulaca_brain/.venv/` (Python
3.11.15 in the current checkout), but creating your own is recommended.

**Database:** SQLite (file-based, no server). Default
`sqlite:///./data/simulaca.db` — relative to the working directory you
launch uvicorn from (typically `simulaca_brain/data/simulaca.db`). The
file is created automatically and is **gitignored**.

### Frontend (Node)

- Node.js 18+ (Node 24 / npm 11 used during development)
- React 19, Vite 6, TypeScript ~5.7, Tailwind CSS 4

### Ollama + LLM model

- **Ollama** (local LLM server) — see [Section 7](#7-ollama-setup)
- Installed model: **`llama3.2:latest`** (3.2B parameters, `Q4_K_M`)
- Ollama API used: `POST http://localhost:11434/api/generate`
  (JSON output, `stream: false`, system prompt)

### GPU / CUDA

**GPU acceleration is not required by the current implementation.** The
code contains no CUDA/GPU-specific logic; inference runs on whatever
Ollama is configured to use (typically CPU, optionally GPU). A 3B model
runs comfortably on CPU.

### Environment variables

All configuration lives in `app/core/config.py` (pydantic-settings). Every
variable uses the **`SIMULACA_` prefix**, is optional, and has a safe
default. Environment variables are read directly, or from a `.env` file in
the directory you run the server from.

| Variable | Default | Purpose |
|----------|---------|---------|
| `SIMULACA_DATABASE_URL` | `sqlite:///./data/simulaca.db` | SQLite location (relative to cwd) |
| `SIMULACA_LLM_PROVIDER` | `ollama` | LLM backend name (`ollama` supported) |
| `SIMULACA_LLM_MODEL` | `llama3.2:latest` | Model served to Ollama |
| `SIMULACA_LLM_BASE_URL` | *(empty)* | Optional override; falls back to `SIMULACA_OLLAMA_BASE_URL` |
| `SIMULACA_OLLAMA_BASE_URL` | `http://localhost:11434` | Default Ollama endpoint |
| `SIMULACA_LLM_TIMEOUT_SECONDS` | `10.0` | Per-request LLM timeout |
| `SIMULACA_PLANNER_TYPE` | `rules` | `rules` or `llm` |
| `SIMULACA_LLM_FALLBACK_TO_RULES` | `true` | Fall back to `RuleBasedPlanner` on LLM failure |
| `SIMULACA_API_PREFIX` | `/api/v1` | API route prefix |
| `SIMULACA_ENVIRONMENT` | `development` | `development` / `testing` / `staging` / `production` |
| `SIMULACA_DEBUG` | `false` | FastAPI debug flag |
| `SIMULACA_LOG_LEVEL` | `INFO` | Root logging level |
| `SIMULACA_APP_NAME` / `SIMULACA_APP_VERSION` | “Simulaca Brain” / `0.1.0` | API metadata |

For the V0.7 LLM brain, the operational set is:

```dotenv
SIMULACA_LLM_PROVIDER=ollama
SIMULACA_LLM_MODEL=llama3.2:latest
SIMULACA_LLM_BASE_URL=http://localhost:11434
SIMULACA_LLM_TIMEOUT_SECONDS=10
SIMULACA_PLANNER_TYPE=llm
SIMULACA_LLM_FALLBACK_TO_RULES=true
```
---

## 6. First-Time Installation

### 1. Clone

```bash
git clone <your-repo-url> simulaca
cd simulaca
```

### 2. Backend environment

```bash
cd simulaca_brain
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

> If `uv` is available you can instead run `uv pip install -r simulaca_brain/requirements.txt`.

### 3. Frontend (optional but recommended for the dashboard)

The backend serves pre-built dashboard assets from `simulaca_dashboard/dist`.
To build (or rebuild after editing the dashboard):

```bash
cd simulaca_dashboard
npm install
npm run build
cd ..
```

> The `dist/` folder must exist for the backend to serve the dashboard at
> `/`. If you only care about the REST API and `/docs`, you can skip this
> and run the backend alone.

### 4. Configure environment (optional)

All configuration is optional (defaults are safe). For the LLM brain,
create a `.env` file in the working directory you launch uvicorn from
(see [Section 5](#5-requirements) for the full variable table):

```dotenv
SIMULACA_PLANNER_TYPE=llm
SIMULACA_LLM_MODEL=llama3.2:latest
SIMULACA_LLM_BASE_URL=http://localhost:11434
SIMULACA_LLM_TIMEOUT_SECONDS=10
SIMULACA_LLM_FALLBACK_TO_RULES=true
```

(Replace that awkward sentence — the `.env` simply lives wherever you
launch uvicorn.)

---

## 7. Ollama Setup

Ollama is the local LLM provider for the **V0.7 brain**. It serves
`llama3.2:latest` on `http://localhost:11434`.

### Install

See https://ollama.com — on most Linux systems:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Verify the CLI

```bash
ollama --version
```

### List installed models

```bash
ollama list
```

Expected output includes:

```text
llama3.2:latest   3.2B   Q4_K_M    ...
```

### Pull the model (only if missing)

```bash
ollama pull llama3.2
```

### Start the server (if not already running)

```bash
ollama serve
```

### Verify the HTTP API

```bash
curl http://localhost:11434/api/tags
```

A successful response is JSON listing your models, e.g.:

```json
{"models":[{"name":"llama3.2:latest", ...}]}
```

> Ollama is only needed when the planner is `llm`. In rule-based mode the
> backend never contacts Ollama (the provider is constructed lazily and no
> request is made).

---

## 8. Daily Startup Guide — Returning to the Project

This is the section to re-read after a break. Three steps.

### Terminal 1 — Ollama

Only if the Ollama server is not already running:

```bash
ollama serve
```

Quick sanity check:

```bash
curl http://localhost:11434/api/tags
```

### Terminal 2 — Simulaca backend

```bash
cd ~/Git/simulaca/simulaca_brain
source .venv/bin/activate
SIMULACA_PLANNER_TYPE=llm SIMULACA_LLM_MODEL=llama3.2:latest uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Omit `SIMULACA_PLANNER_TYPE=llm` if you want the default **rule-based**
  planner (no Ollama required).
- `--reload` is optional (auto-restart on code edits).

### Browser

| What | URL |
|------|-----|
| Dashboard | http://127.0.0.1:8000/ |
| API docs (Swagger) | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/api/v1/health |

#### Optional — run the dashboard in dev mode (Vite)

For live frontend reloading instead of the pre-built `dist/`:

```bash
cd ~/Git/simulaca/simulaca_dashboard
npm install
npm run dev
```

dev server proxies `/api` → `http://127.0.0.1:8000` (see
`vite.config.ts`), so the backend must be running in Terminal 2.
---

## 9. Verifying the System

Work through this checklist after starting everything.

1. **Ollama responds** — `curl http://localhost:11434/api/tags` returns JSON.
2. **Model exists** — the JSON contains `"name":"llama3.2:latest"`.
3. **FastAPI starts** — uvicorn prints `Application startup complete.` and
   `Uvicorn running on http://127.0.0.1:8000`.
4. **API docs** — http://127.0.0.1:8000/docs loads the Swagger UI.
5. **Health** — `curl http://127.0.0.1:8000/api/v1/health` returns
   `{"status":"ok", ...}`.
6. **Dashboard loads** — http://127.0.0.1:8000/ shows the Simulaca Dashboard.
7. **Agent CRUD** — `curl -X POST http://127.0.0.1:8000/api/v1/agents -H "Content-Type: application/json" -d '{"name":"Alice","needs":{"thirst":95}}'` returns 201 with an agent id.
8. **World endpoint** — `curl http://127.0.0.1:8000/api/v1/world` returns
   `{"locations":…,"entities":…}`.
9. **Brain status** — `curl http://127.0.0.1:8000/api/v1/brain/status`
   returns planner config (with `SIMULACA_PLANNER_TYPE=llm` it should
   report `planner:"llm"` and the model name).
10. **Simulation steps** — `curl -X POST http://127.0.0.1:8000/api/v1/simulation/step` returns tick `1` and `agents_updated`.
11. **Agent plan** — `curl http://127.0.0.1:8000/api/v1/agents/<id>/plan`
    returns the generated `ActionPlan` steps (after stepping).
12. **Decision metadata** — `curl http://127.0.0.1:8000/api/v1/agents/<id>/decision` returns planner/goal/status/latency.
13. **Plan executes** — after two steps, the decision log
    (`GET /api/v1/logs?agent_id=<id>`) shows the executed actions and the
    plan status becomes `completed`.

> In **rule-based mode** the plan is still generated and executed, just by
> `RuleBasedPlanner` instead of the LLM. In **LLM mode** with Ollama down,
> `SIMULACA_LLM_FALLBACK_TO_RULES=true` produces a rule-based plan and the
> decision reports `status:"fallback"`.

---

## 10. Running Tests

From the repository root or the backend directory:

```bash
cd ~/Git/simulaca/simulaca_brain
.venv/bin/python -m pytest -q
```

(or activate the venv first, then plain `pytest`).

### Which tests need what

- **All current tests run offline.** None of the committed tests require
  Ollama or a live LLM server.
- The suite covers agent CRUD, needs/state, memory + recall, the
  simulation clock/engine/lifecycle, world persistence, events,
  exceptions, health, and the no-op cognition pipeline skeleton.
- The **LLM planner path is not yet covered by committed tests** — that is
  the remaining V0.7 work (the `FakeLLMProvider` in
  `app/core/llm/fake.py` exists precisely for offline planner tests:
  valid responses, invalid JSON, unknown actions/targets, timeouts, and
  fallback).

---

## 11. Planner Modes

The simulation uses exactly one planner, chosen by `SIMULACA_PLANNER_TYPE`.

### Rule-based (default) — `SIMULACA_PLANNER_TYPE=rules`

- `RuleBasedPlanner` maps a goal to a minimal plan deterministically
  (e.g. `drink` → `[move → river (if needed), drink → river]`).
- No LLM, no Ollama, fully offline, deterministic.
- Always available and used as the fallback.

### LLM — `SIMULACA_PLANNER_TYPE=llm`

- `LLMPlanner` builds a bounded `DecisionContext`, prompts the local LLM
  (`Ollama` → `llama3.2:latest`), and asks for a structured `ActionPlan`.
- The response must be valid JSON matching the `ActionPlan` schema; it is
  parsed (`llm_response_parser.py`) then validated by `PlanValidator`
  before anything runs.
- If the LLM answers with invalid JSON, an unknown action, or an invented
  target, the plan is **rejected — nothing executes**.

### Fallback behavior

`SIMULACA_LLM_FALLBACK_TO_RULES=true` (the default) means: if Ollama is
unavailable, times out, or returns an unusable plan, the service logs the
failure and falls back to `RuleBasedPlanner`. The `BrainStateStore` records
`status: "fallback"` plus `fallback_reason`, so fallbacks are visible, not
silent. Set `SIMULACA_LLM_FALLBACK_TO_RULES=false` to surface LLM failures
instead of falling back.
---

## 12. LLM Brain

A single agent decision goes through:

```
Context (agent state + needs + memory + perception + goal)
      ↓
LLM Planner (Ollama / llama3.2:latest)
      ↓
Structured ActionPlan (JSON)
      ↓
PlanValidator
      ↓
PlanExecutor (one step per tick)
      ↓
World + Needs change
```

Invariants of the V0.7 brain:

- **The LLM never executes actions, never touches the database, and never
  writes to the world.** It returns data — a plan.
- The prompt includes only a bounded decision context; internal prompts,
  raw LLM output and chain-of-thought are **not exposed** through the API.
- The API exposes only: planner, model, goal, plan steps, status, latency,
  fallback status, and a short `reasoning_summary`.
- Multi-step plans persist in `BrainStateStore` and are consumed **one
  step per tick** (Alice: tick 1 `move → river`, tick 2 `drink → river`).

---

## 13. API Reference

All routes are served under the configured prefix (`/api/v1` by default).
Interactive docs at `/docs`.

### Health

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/health` | Liveness: status, app name/version, environment |

### Agents

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/agents` | Create agent `{name, needs?}` |
| GET | `/api/v1/agents` | List agents (`limit`, `offset` query params) |
| GET | `/api/v1/agents/{agent_id}` | Get one agent |
| PATCH | `/api/v1/agents/{agent_id}` | Update `name` and/or `needs` |
| DELETE | `/api/v1/agents/{agent_id}` | Delete one agent |
| GET | `/api/v1/agents/{agent_id}/perception` | Agent's perceived location, nearby locations/entities |
| GET | `/api/v1/agents/{agent_id}/context` | Minimal decision context (perception + location) |
| GET | `/api/v1/agents/{agent_id}/events` | Activity timeline for one agent (`limit`, `offset` query params; ordered oldest → newest) |

### Memory

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/agents/{agent_id}/memories` | List recent memories |
| POST | `/api/v1/agents/{agent_id}/memories` | Create memory `{memory_type, content, attributes?}` |
| GET | `/api/v1/agents/{agent_id}/memory/recall` | Recall memories relevant to `goal` |
| DELETE | `/api/v1/agents/memories/{memory_id}` | Delete one memory |
### Brain (V0.7)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/brain/status` | Planner config, model, fallback flag, LLM availability, latest decisions, latest LLM request |
| GET | `/api/v1/agents/{agent_id}/decision` | Latest decision metadata (planner, goal, status, latency, fallback) |
| GET | `/api/v1/agents/{agent_id}/plan` | Latest validated `ActionPlan` (goal, steps, reasoning summary) |

> Brain responses never include internal prompts or raw chain-of-thought.

### Simulation

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/simulation/step` | Advance one tick (advances needs + executes one step per agent) |
| POST | `/api/v1/simulation/start` | Start the automatic 2-second tick loop |
| POST | `/api/v1/simulation/stop` | Stop the automatic tick loop |

### Decision logs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/logs` | Recent decision logs (`agent_id`, `limit` query params) |
| DELETE | `/api/v1/logs` | Clear all decision logs |

### World

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/world` | World summary (location/entity counts) |
| GET | `/api/v1/world/locations` | List all locations |
| GET | `/api/v1/world/locations/{location_id}` | Get one location |
| GET | `/api/v1/world/entities` | List all entities |
---

## 14. Dashboard

The developer dashboard is a React (TypeScript + Vite + Tailwind) app in
`simulaca_dashboard/`. Its built output (`dist/`) is served by the FastAPI
backend at `http://127.0.0.1:8000/`.

### Current panels

| Panel | What it shows |
|-------|---------------|
| API status | Backend health (`GET /api/v1/health`) |
| Simulation controls | Step / Start / Stop + current tick/goal/action |
| Create agent | Create an agent by name (initial needs are optional) |
| Agent list | All agents, click to select |
| Agent detail | Selected agent: name, id, created/updated, **needs** (hunger, thirst, fatigue, social, safety, comfort) |
| Activity / Agent timeline | Selected agent: observable events over time (need changes, goal changes, planner decisions, plan creation, action execution, state changes, memory creation, errors, fallbacks) |
| Decision logs | Recent `action` + `reason` for each agent tick |
| Memory panel | Recent memories for the selected agent (delete supported) |
| Recall panel | Recall goal + recalled memories for the selected agent |

### Not yet in the dashboard

- **Brain / LLM panel.** The backend Brain endpoints exist
  (`/api/v1/brain/status`, `/agents/{id}/decision`, `/agents/{id}/plan`)
  and the `AgentDetail` view is the intended home for it, but the
  frontend does not render planner/model/goal/ActionPlan/latency/
  fallback yet. This is the remaining V0.7 dashboard work.

> When you change the dashboard source, rebuild with
> `cd simulaca_dashboard && npm run build` so the backend serves the new
> assets (the backend only serves `dist/`).

---

## 15. Development Workflow

Recommended order when adding a feature:

1. **Inspect the architecture** — read the relevant `app/modules/*` and
   the DI graph in `app/api/dependencies.py`.
2. **Add/update domain models** — Pydantic models in the module (e.g.
   `ActionPlan` in `app/modules/cognition/action_plan.py`).
3. **Add a service** — business logic in `app/modules/...` (never in the
   route or the repository).
4. **Add a repository / persistence if required** — SQLite adapters
   follow the existing `repo.initialize()` + protocol pattern.
5. **Expose via API if required** — add an endpoint under `app/api/` and
   register it in `app/api/router.py`.
6. **Add tests** — offline tests under `simulaca_brain/tests/`; use
   `FakeLLMProvider` for anything that touches the LLM.
7. **Update the dashboard if user-visible** — new component in
   `simulaca_dashboard/src/components`, then `npm run build`.
8. **Run the test suite** — `.venv/bin/python -m pytest -q`.
9. **Run the simulation manually** — start the server, create an agent,
   step the simulation, inspect `/agents/{id}/plan` and `/logs`.
10. **Update this README** when behavior or endpoints change.

---

## 16. Troubleshooting

### Dashboard shows 404

Check that the pre-built assets exist and are being served:

```bash
ls ~/Git/simulaca/simulaca_dashboard/dist/index.html
curl -I http://127.0.0.1:8000/
```

If `dist/` is missing, build it:

```bash
cd ~/Git/simulaca/simulaca_dashboard && npm install && npm run build
```

The backend mounts the dashboard only when `simulaca_dashboard/dist`
exists (see `app/main.py`).

### Ollama connection error

```bash
ollama list
curl http://localhost:11434/api/tags
```

If the curl fails, start Ollama (`ollama serve`) and re-check. If Ollama is
running on a non-default host/port, set:

```dotenv
SIMULACA_LLM_BASE_URL=http://<host>:<port>
```

### Model not found

```bash
ollama list
```

If `llama3.2:latest` is missing:

```bash
ollama pull llama3.2
```

Then verify: `curl http://localhost:11434/api/tags`.

### Agent creation returns 500

The API returns a structured `ErrorResponse` by design; the real cause is
in the server logs (and the browser/terminal running uvicorn). Reproduce
the call and read the traceback printed by uvicorn, or run pytest:

```bash
cd ~/Git/simulaca/simulaca_brain && .venv/bin/python -m pytest -q
```

### Port 8000 already in use

Identify and (optionally) kill the process listening on 8000:

```bash
lsof -i :8000            # list the PID(s)
ss -ltnp 'sport = :8000' # alternative
kill <PID>               # or: kill -9 <PID>
```

Then start uvicorn again with a free port or `--port 8080`.

### LLM planner falls back to rules unexpectedly

With `SIMULACA_PLANNER_TYPE=llm`, check:

1. `curl http://localhost:11434/api/tags` — Ollama must be reachable.
2. `curl -X POST http://localhost:11434/api/generate` behaves.
3. `GET /api/v1/brain/status` shows `planner:"llm"`, the model, and
   `llm_available:true`.
4. `GET /api/v1/agents/{id}/decision` shows `status:"fallback"` and a
   `fallback_reason` when a fallback happened.
---

## 17. Development Notes

Architectural rules that should not be broken:

- **Do not bypass `PlanValidator`.** Every `ActionPlan`, LLM-generated or
  rule-generated, must pass validation before any step executes.
- **Do not let the LLM directly modify world state.** The planner returns
  a plan; only `PlanExecutor` mutates needs/locations.
- **No database logic inside planners.** Persistence lives in
  repositories (`app/modules/*/repository.py`); planners are pure.
- **Keep the simulation core independent from FastAPI.** Services and
  modules do not import the API; the API depends on services.
- **Keep the LLM provider abstract.** Code depends on the
  `LLMProvider` protocol (`app/core/llm/base.py`); `OllamaProvider`,
  `FakeLLMProvider`, and future backends are pluggable.
- **Preserve `RuleBasedPlanner` as a fallback.** It is the deterministic,
  offline-safe baseline and the default planner.
- **Use the structured `ActionPlan`.** Natural-language LLM responses are
  never executed; the parser + Pydantic turn them into `ActionPlan`s.
- **Add tests for new behavior.** New endpoints/services/planners need
  offline test coverage.
- **Configuration only via `Settings`.** No `os.environ` reads in
  business logic — add fields to `app/core/config.py`.

---

## 18. Roadmap

Current (implemented):

- V0.1 Foundation — FastAPI service, config, SQLite repositories.
- V0.2 Living Agent — needs, tick-driven state updates, decision logs.
- V0.3 Episodic Memory — memory recording + working memory.
- V0.4 Memory Recall — goal-based recall.
- V0.5 World State & Perception — locations, entities, connections,
  perception service.
- V0.6 Goal-Oriented Planner — `ActionPlan`, `RuleBasedPlanner`,
  `PlanValidator`, `PlanExecutor` (one step per tick).
- V0.7 LLM Brain — Ollama provider, `LLMPlanner`, LLM pipeline wiring,
  Brain API. **In progress** (dashboard panel + planner tests + a live
  Ollama end-to-end run remain).

Future (planned — none of these exist yet):

- **V0.8 Reflection** — agents review previous outcomes.
- **V0.9 Long-Term Memory** — improved semantic memory and retrieval.
- **V1.0 Multi-Agent Interaction** — NPCs communicate and influence one
  another.
- **V1.1 Economy / Jobs** — agents have jobs, resources, money,
  production and trade.
- **V1.2 Relationships** — friendships, rivalries, families and social
  groups.
- **V1.3 Learning** — agents improve behavior from experience.
- **V1.4 Reinforcement Learning** — RL for action/decision learning.
- **V2.0 Unreal Engine Integration** — connect the brain to a visual 3D
  world.

---

## 19. Design Philosophy

Simulaca is designed as a **layered artificial-life system**. The goal is
not to bolt an LLM onto an NPC; it is to build agents with:

- needs
- perception
- memory
- goals
- planning
- actions and consequences
- reflection
- learning

The LLM is **one component of cognition**, not the whole agent. Every
cognitive output is a *proposal* that must pass domain validation before it
can mutate the world, which keeps the simulation predictable, debuggable,
and safe to extend — from pure rule-based agents today to learned behavior
later.

---

*Operational manual — keep this file in sync with the code. When in doubt,
verify against `app/core/config.py`, `app/api/router.py`, and
`simulaca_dashboard/src/`.*
