import pytest
from fastapi.testclient import TestClient


def test_api_health(client: TestClient):
    """Verify /health endpoint returns 200 with service metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data
    assert "database_connected" in data
    assert "gemini_configured" in data


def test_api_create_incident(client: TestClient):
    """Verify POST /api/v1/incidents creates incident and returns 201."""
    payload = {
        "title": "Authentication timeout",
        "description": "Users are receiving 504 errors during login and token refresh requests are timing out.",
        "service": "auth",
        "source": "manual"
    }
    response = client.post("/api/v1/incidents", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "incident_id" in data
    assert data["status"] in ("INVESTIGATING", "AWAITING_APPROVAL")


def test_api_get_incident_detail(client: TestClient):
    """Verify GET /api/v1/incidents/{id} returns comprehensive incident details."""
    # Create incident first
    create_resp = client.post("/api/v1/incidents", json={
        "title": "Auth 504 errors",
        "description": "Authentication gateway timeout.",
        "service": "auth"
    })
    inc_id = create_resp.json()["incident_id"]

    # Get incident
    get_resp = client.get(f"/api/v1/incidents/{inc_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == inc_id
    assert data["service"] == "auth"
    assert data["status"] == "AWAITING_APPROVAL"
    assert data["recommended_action"] == "restart_service"
    assert data["approval_required"] is True
    assert data["pending_action"] is not None
    assert data["pending_action"]["name"] == "restart_service"


def test_api_get_incident_events(client: TestClient):
    """Verify GET /api/v1/incidents/{id}/events returns chronological audit events."""
    create_resp = client.post("/api/v1/incidents", json={
        "title": "Auth 504 errors",
        "description": "Authentication gateway timeout.",
        "service": "auth"
    })
    inc_id = create_resp.json()["incident_id"]

    events_resp = client.get(f"/api/v1/incidents/{inc_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert isinstance(events, list)
    assert len(events) >= 5

    event_types = [e["event_type"] for e in events]
    assert "INCIDENT_CREATED" in event_types
    assert "HEALTH_CHECK" in event_types
    assert "RAG_SEARCH" in event_types


def test_api_approve_action(client: TestClient):
    """Verify approving a pending action transitions incident to RESOLVED."""
    create_resp = client.post("/api/v1/incidents", json={
        "title": "Auth timeout",
        "description": "Token refresh timeout.",
        "service": "auth"
    })
    inc_id = create_resp.json()["incident_id"]

    # Approve action
    approve_resp = client.post(
        f"/api/v1/incidents/{inc_id}/approve",
        json={"approved": True, "reason": "Approved by on-call engineer"}
    )
    assert approve_resp.status_code == 200
    data = approve_resp.json()
    assert data["status"] == "RESOLVED"
    assert data["resolved_at"] is not None


def test_api_reject_action(client: TestClient):
    """Verify rejecting a pending action transitions incident to REJECTED."""
    create_resp = client.post("/api/v1/incidents", json={
        "title": "Auth timeout",
        "description": "Token refresh timeout.",
        "service": "auth"
    })
    inc_id = create_resp.json()["incident_id"]

    # Reject action
    reject_resp = client.post(
        f"/api/v1/incidents/{inc_id}/reject",
        json={"reason": "Wait for additional evidence"}
    )
    assert reject_resp.status_code == 200
    data = reject_resp.json()
    assert data["status"] == "REJECTED"


def test_api_idempotent_approval_rejection(client: TestClient):
    """Verify that approving/rejecting an already resolved incident returns 409 Conflict."""
    create_resp = client.post("/api/v1/incidents", json={
        "title": "Auth timeout",
        "description": "Token refresh timeout.",
        "service": "auth"
    })
    inc_id = create_resp.json()["incident_id"]

    # First approve
    client.post(f"/api/v1/incidents/{inc_id}/approve", json={"approved": True})

    # Second approval attempt should fail with 409
    dup_resp = client.post(f"/api/v1/incidents/{inc_id}/approve", json={"approved": True})
    assert dup_resp.status_code == 409
    assert "already in terminal state" in dup_resp.json()["detail"]


def test_api_missing_incident(client: TestClient):
    """Verify 404 response for nonexistent incident."""
    resp = client.get("/api/v1/incidents/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
