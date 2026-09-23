"""
End-to-End Acceptance Scenario Test (Prompt Section 30).
Validates full lifecycle:
1. Incident Creation & Investigation
2. Telemetry health, logs, RAG retrieval
3. LLM diagnosis & risk policy gating
4. Pause at AWAITING_APPROVAL for restart_service (HIGH risk)
5. Approval -> Action Execution -> Verification -> RESOLVED
6. Rejection flow -> REJECTED (no action executed)
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_final_acceptance_scenario():
    with TestClient(app) as client:
        # Step 1: Submit incident
        create_payload = {
            "title": "Authentication timeout",
            "description": "Users are receiving 504 errors during login and token refresh requests are timing out.",
            "service": "auth",
            "source": "manual"
        }
        create_res = client.post("/api/v1/incidents", json=create_payload)
        assert create_res.status_code == 201
        inc_data = create_res.json()
        inc_id = inc_data["incident_id"]
        assert inc_data["status"] == "AWAITING_APPROVAL"

        # Step 2: Verify paused state and pending action
        get_res = client.get(f"/api/v1/incidents/{inc_id}")
        assert get_res.status_code == 200
        detail = get_res.json()
        assert detail["status"] == "AWAITING_APPROVAL"
        assert detail["severity"] == "HIGH"
        assert detail["recommended_action"] == "restart_service"
        assert detail["action_risk"] == "HIGH"
        assert detail["approval_required"] is True
        assert detail["pending_action"]["name"] == "restart_service"
        assert detail["pending_action"]["risk"] == "HIGH"

        # Step 3: Verify audit event stream
        events_res = client.get(f"/api/v1/incidents/{inc_id}/events")
        assert events_res.status_code == 200
        events = events_res.json()
        event_types = [e["event_type"] for e in events]
        assert "INCIDENT_CREATED" in event_types
        assert "INVESTIGATING" in event_types
        assert "HEALTH_CHECK" in event_types
        assert "LOGS_COLLECTED" in event_types
        assert "RAG_SEARCH" in event_types
        assert "LLM_ANALYSIS" in event_types
        assert "ACTION_PROPOSED" in event_types
        assert "APPROVAL_REQUESTED" in event_types
        assert "ACTION_EXECUTED" not in event_types

        # Step 4: Approve the action
        approve_res = client.post(
            f"/api/v1/incidents/{inc_id}/approve",
            json={"approved": True, "reason": "Approved by on-call engineer"}
        )
        assert approve_res.status_code == 200
        approved_detail = approve_res.json()
        assert approved_detail["status"] == "RESOLVED"
        assert approved_detail["resolved_at"] is not None

        # Step 5: Verify post-approval event sequence
        events_after = client.get(f"/api/v1/incidents/{inc_id}/events").json()
        after_types = [e["event_type"] for e in events_after]
        assert "ACTION_APPROVED" in after_types
        assert "ACTION_EXECUTED" in after_types
        assert "VERIFICATION" in after_types
        assert "RESOLVED" in after_types

        # Step 6: Test rejection separately on a new incident
        create_res2 = client.post("/api/v1/incidents", json=create_payload)
        inc_id2 = create_res2.json()["incident_id"]

        reject_res = client.post(
            f"/api/v1/incidents/{inc_id2}/reject",
            json={"reason": "Rejected by on-call operator"}
        )
        assert reject_res.status_code == 200
        rejected_detail = reject_res.json()
        assert rejected_detail["status"] == "REJECTED"

        events_rejected = client.get(f"/api/v1/incidents/{inc_id2}/events").json()
        rej_types = [e["event_type"] for e in events_rejected]
        assert "ACTION_REJECTED" in rej_types
        assert "REJECTED" in rej_types
        assert "ACTION_EXECUTED" not in rej_types
        assert "RESOLVED" not in rej_types
