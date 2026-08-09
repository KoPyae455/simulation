"""
Top-level API router.

Aggregates every module's router under one object so app.main only
ever mounts a single router. New modules (agent, memory, cognition,
world) register their routers here as they gain endpoints -- main.py
never needs to change again for routing purposes.
"""

from fastapi import APIRouter

from app.api.brain import router as brain_router
from app.api.health import router as health_router
from app.api.agents import router as agents_router
from app.api.logs import router as logs_router
from app.api.memories import router as memories_router
from app.api.world import router as world_router
from app.api.simulation import router as simulation_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(agents_router, tags=["agents"])
api_router.include_router(simulation_router, tags=["simulation"])
api_router.include_router(logs_router, tags=["logs"])
api_router.include_router(memories_router, tags=["memories"])
api_router.include_router(world_router, tags=["world"])
api_router.include_router(brain_router, tags=["brain"])
