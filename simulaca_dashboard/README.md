# Simulaca Dashboard

A lightweight React + Vite + TypeScript dashboard for debugging and visualizing the Simulaca simulation backend.

## Overview

This frontend consumes the existing FastAPI backend without modifying any API endpoints. It is designed for simple developer use:

- View agents
- Create agents
- Delete agents
- Inspect agent details
- Display internal state values
- Show API health/status

## Setup

From the `simulaca_dashboard` directory:

```bash
npm install
```

## Development

```bash
npm run dev
```

Then open the local Vite URL shown in the terminal.

## Build

```bash
npm run build
```

## Preview

```bash
npm run preview
```

## Run the full project with backend hosting the dashboard

1. Build the frontend assets:

```bash
npm install
npm run build
```

2. Activate the backend Python environment from the repo root:

```bash
cd ..
source simulaca_brain/.venv/bin/activate
```

3. Install backend dependencies if needed:

```bash
uv pip install -r simulaca_brain/requirements.txt
```

4. Start the backend server using `uv` and `uvicorn`:

```bash
uv uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

5. Open the dashboard in your browser:

```text
http://127.0.0.1:8000/
```

## Notes

- The dashboard is intentionally simple and not a final UI.
- When served from the backend, the dashboard is available at `/` and API endpoints remain under `/api/v1`.
- Tailwind CSS is used for basic styling.
