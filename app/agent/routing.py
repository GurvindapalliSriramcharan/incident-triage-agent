from typing import Literal
from app.agent.state import IncidentState


def route_risk_gate(state: IncidentState) -> Literal["request_approval", "execute_action"]:
    """
    Direct workflow based on risk assessment.
    HIGH or CRITICAL risk actions strictly require human approval.
    """
    if state.get("approval_required", True):
        return "request_approval"
    return "execute_action"


def route_approval_decision(state: IncidentState) -> Literal["execute_action", "handle_rejection"]:
    """
    Direct workflow based on human approval decision.
    """
    if state.get("approval_status") == "APPROVED":
        return "execute_action"
    return "handle_rejection"


def route_verification(state: IncidentState) -> Literal["complete_resolved", "escalate"]:
    """
    Direct workflow based on post-remediation health verification.
    """
    if state.get("final_status") == "RESOLVED":
        return "complete_resolved"
    return "escalate"
