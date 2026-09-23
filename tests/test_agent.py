import uuid
import pytest
from app.agent.graph import (
    build_incident_graph,
    resume_incident_workflow,
    run_incident_workflow,
)
from app.db.repositories import IncidentEventRepository, IncidentRepository
from app.tools.actions import execute_simulated_action
from langgraph.checkpoint.memory import MemorySaver


def test_agent_high_risk_pauses_for_approval():
    """Verify that a high-risk incident pauses at AWAITING_APPROVAL."""
    inc_id = str(uuid.uuid4())
    run_incident_workflow(
        incident_id=inc_id,
        title="Authentication timeout",
        description="Users are receiving 504 errors during login and token refresh requests are timing out.",
        service="auth",
        source="datadog"
    )

    incident = IncidentRepository.get(inc_id)
    assert incident is not None
    assert incident["status"] == "AWAITING_APPROVAL"
    assert incident["recommended_action"] == "restart_service"
    assert incident["severity"] in ("HIGH", "CRITICAL")

    # Verify audit events up to interrupt
    events = IncidentEventRepository.get_by_incident(inc_id)
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


def test_agent_approval_resumes_and_resolves():
    """Verify that approving a paused incident executes action, verifies, and resolves."""
    inc_id = str(uuid.uuid4())
    run_incident_workflow(
        incident_id=inc_id,
        title="Authentication timeout",
        description="Users are receiving 504 errors during login.",
        service="auth"
    )

    # Now approve
    resume_incident_workflow(
        incident_id=inc_id,
        approved=True,
        reason="Approved by SRE on-call engineer"
    )

    incident = IncidentRepository.get(inc_id)
    assert incident["status"] == "RESOLVED"
    assert incident["resolved_at"] is not None

    events = IncidentEventRepository.get_by_incident(inc_id)
    event_types = [e["event_type"] for e in events]
    assert "ACTION_APPROVED" in event_types
    assert "ACTION_EXECUTED" in event_types
    assert "VERIFICATION" in event_types
    assert "RESOLVED" in event_types


def test_agent_rejection_aborts_execution():
    """Verify that rejecting a paused incident skips action execution and marks REJECTED."""
    inc_id = str(uuid.uuid4())
    run_incident_workflow(
        incident_id=inc_id,
        title="Authentication timeout",
        description="Users are receiving 504 errors during login.",
        service="auth"
    )

    # Reject proposed action
    resume_incident_workflow(
        incident_id=inc_id,
        approved=False,
        reason="Rejected: waiting for scheduled maintenance window"
    )

    incident = IncidentRepository.get(inc_id)
    assert incident["status"] == "REJECTED"

    events = IncidentEventRepository.get_by_incident(inc_id)
    event_types = [e["event_type"] for e in events]
    assert "ACTION_REJECTED" in event_types
    assert "REJECTED" in event_types
    assert "ACTION_EXECUTED" not in event_types
    assert "RESOLVED" not in event_types


def test_agent_low_risk_auto_executes():
    """Verify that low-risk actions (e.g. clear_cache) auto-execute without pausing."""
    inc_id = str(uuid.uuid4())

    # Create initial incident
    IncidentRepository.create(
        title="Stale Redis cache keys",
        description="Cache needs eviction for auth tokens.",
        service="auth"
    )

    # Test execution graph when action proposed is clear_cache (LOW risk)
    from app.agent.nodes import (
        collect_health_node,
        execute_action_node,
        propose_action_node,
        verify_resolution_node,
        complete_resolved_node,
    )

    state = {
        "incident_id": inc_id,
        "title": "Stale Redis cache keys",
        "description": "Cache needs eviction.",
        "service": "auth",
        "source": "manual",
        "recommended_action": "clear_cache",
        "action_risk": "LOW",
        "approval_required": False
    }

    # Propose action node confirms low risk doesn't require approval
    propose_res = propose_action_node(state)
    assert propose_res["approval_required"] is False
    assert propose_res["action_risk"] == "LOW"

    # Action executes directly
    state.update(propose_res)
    exec_res = execute_action_node(state)
    assert exec_res["status"] == "REMEDIATING"
    assert exec_res["action_result"]["success"] is True

    # Verification passes and resolves
    state.update(exec_res)
    verify_res = verify_resolution_node(state)
    assert verify_res["final_status"] == "RESOLVED"


def test_agent_verification_failure_escalates(monkeypatch):
    """Verify that if post-remediation health check fails, the workflow transitions to ESCALATED."""
    from app.agent.nodes import verify_resolution_node, escalate_node

    inc_id = str(uuid.uuid4())
    IncidentRepository.create(
        title="Payment webhook failure",
        description="Webhooks failing continuously.",
        service="payments",
        incident_id=inc_id
    )

    # Force simulated health check to return UNHEALTHY
    monkeypatch.setattr(
        "app.agent.nodes.check_service_health",
        lambda service, override_status=None: {"status": "UNHEALTHY", "service": service}
    )

    state = {
        "incident_id": inc_id,
        "service": "payments",
        "action_result": {"success": True, "stabilized": False}
    }

    verify_res = verify_resolution_node(state)
    assert verify_res["final_status"] == "FAILED"

    state.update(verify_res)
    esc_res = escalate_node(state)
    assert esc_res["final_status"] == "ESCALATED"

    incident = IncidentRepository.get(inc_id)
    assert incident["status"] == "ESCALATED"
