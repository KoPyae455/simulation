"""Integration tests for the initial agent, cognition, and memory workflows."""


def test_create_agent(client):
    created = client.post("/api/v1/agents", json={"name": "Asha", "needs": {"hunger": 80, "rest": 10, "safety": 5, "social": 20}})
    assert created.status_code == 201
    agent = created.json()
    assert agent["name"] == "Asha"

    fetched = client.get(f"/api/v1/agents/{agent['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == agent["id"]


def test_unknown_agent_returns_structured_not_found(client):
    response = client.get("/api/v1/agents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error_code"] == "entity_not_found"


def test_update_and_delete_agent(client):
    agent = client.post("/api/v1/agents", json={"name": "Sol"}).json()
    updated = client.patch(f"/api/v1/agents/{agent['id']}", json={"name": "Sola", "needs": {"hunger": 40}})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Sola"
    assert updated.json()["needs"]["hunger"] == 40

    deleted = client.delete(f"/api/v1/agents/{agent['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/agents/{agent['id']}").status_code == 404


def test_empty_or_invalid_update_is_rejected(client):
    agent = client.post("/api/v1/agents", json={"name": "Nia"}).json()
    assert client.patch(f"/api/v1/agents/{agent['id']}", json={}).status_code == 422
    assert client.patch(f"/api/v1/agents/{agent['id']}", json={"needs": {"hunger": 101}}).status_code == 422
