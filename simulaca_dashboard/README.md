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

## Notes

- The dashboard is intentionally simple and not a final UI.
- It expects the backend API to be available separately.
- Tailwind CSS is used for basic styling.
