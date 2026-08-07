"""HTTP endpoints exposing world state and queries."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import get_world_knowledge_service, get_world_perception_service
from app.modules.world.service import WorldKnowledgeService, WorldPerceptionService

router = APIRouter(prefix="/world")


@router.get("", response_model=dict)
def get_world_state(service: Annotated[WorldKnowledgeService, Depends(get_world_knowledge_service)]):
    """Return a simple world summary (time, weather, counts)."""
    locations = service.list_locations()
    entities = service.list_entities()
    return {"locations": len(locations), "entities": len(entities)}


@router.get("/locations", response_model=list)
def list_locations(service: Annotated[WorldKnowledgeService, Depends(get_world_knowledge_service)]):
    return [loc.model_dump() for loc in service.list_locations()]


@router.get("/locations/{location_id}")
def get_location(location_id: UUID, service: Annotated[WorldKnowledgeService, Depends(get_world_knowledge_service)]):
    return service.get_location(location_id).model_dump()


@router.get("/entities", response_model=list)
def list_entities(service: Annotated[WorldKnowledgeService, Depends(get_world_knowledge_service)]):
    return [e.model_dump() for e in service.list_entities()]
