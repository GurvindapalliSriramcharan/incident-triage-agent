from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class IncidentState(TypedDict):
    """Strongly typed state schema for the Incident Triage LangGraph agent."""
    incident_id: str
    external_id: Optional[str]
    title: str
    description: str
    service: str
    source: str
    severity: Optional[str]
    status: str
    evidence: Dict[str, Any]
    health_results: Dict[str, Any]
    log_results: List[Dict[str, Any]]
    retrieved_runbooks: List[Dict[str, Any]]
    root_cause_hypothesis: Optional[str]
    confidence: Optional[float]
    reasoning_summary: Optional[str]
    recommended_action: Optional[str]
    action_risk: Optional[str]
    approval_required: bool
    approval_status: Optional[str]   # PENDING, APPROVED, REJECTED
    approval_reason: Optional[str]
    action_result: Optional[Dict[str, Any]]
    verification_result: Optional[Dict[str, Any]]
    final_status: str
    error: Optional[str]
