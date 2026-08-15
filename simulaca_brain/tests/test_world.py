"""Unit tests for basic world storage, connections, and perception."""
from datetime import UTC, datetime
from uuid import uuid4

from app.modules.world.repository import SqliteWorldRepository
from app.modules.world.service import WorldKnowledgeService, WorldPerceptionService


def test_create_locations_entities_and_connections(tmp_path) -> None:
    repo = SqliteWorldRepository(tmp_path / "world.sqlite")
    repo.initialize()

    home = repo.create_location("Home", "The agent's home")
    river = repo.create_location("River", "A flowing river")
    shop = repo.create_location("Shop", "A small shop")

    # connect Home <-> River and Home <-> Shop
    repo.connect_locations(home.id, river.id)
    repo.connect_locations(home.id, shop.id)

    locs = repo.list_locations()
    assert {l.name for l in locs} >= {"Home", "River", "Shop"}

    connected = repo.get_connected_locations(home.id)
    assert {c.name for c in connected} >= {"River", "Shop"}

    # create an entity at the river
    ent = repo.create_entity("Water", river.id, {"type": "resource"})
    all_entities = repo.list_entities()
    assert any(e.name == "Water" for e in all_entities)


def test_perception_reports_nearby(tmp_path) -> None:
    repo = SqliteWorldRepository(tmp_path / "world2.sqlite")
    repo.initialize()
    knowledge = WorldKnowledgeService(repo)
    perception = WorldPerceptionService(knowledge, repo)

    home = repo.create_location("Home", None)
    river = repo.create_location("River", None)
    shop = repo.create_location("Shop", None)
    repo.connect_locations(home.id, river.id)
    repo.connect_locations(home.id, shop.id)

    water = repo.create_entity("Water", river.id, {})

    agent_id = uuid4()
    # place agent at Home
    repo.set_agent_location(agent_id, home.id)

    p = perception.perceive(agent_id)
    assert p["location"] == str(home.id)
    # nearby should include river and shop
    names = {l["name"] for l in p["nearby_locations"]}
    assert {"River", "Shop"}.issubset(names)
    # nearby entities should include water
    ents = {e["name"] for e in p["nearby_entities"]}
    assert "Water" in ents
    # nearby resources should be present (V0.9)
    assert "nearby_resources" in p
    res_names = {r["name"] for r in p["nearby_resources"]}
    # Water entity should have been perceived as a resource at the river
