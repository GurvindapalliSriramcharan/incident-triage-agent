import logging
from typing import List
from fastapi import APIRouter, HTTPException, status

from app.agent.graph import run_incident_workflow
from app.db.repositories import IncidentEventRepository, IncidentRepository
from app.schemas.incident import (
    ActionRiskLevel,
    IncidentCreateRequest,
    IncidentCreateResponse,
    IncidentDetailResponse,
    IncidentEventResponse,
    IncidentStatus,
    PendingAction,
)
from app.tools.actions import get_action_policy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post(
    "",
    response_model=IncidentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new incident and initiate autonomous triage"
)
def create_incident(req: IncidentCreateRequest):
    """
    Submit an incident for autonomous investigation, evidence collection,
    RAG runbook lookup, LLM diagnosis, and remediation planning.
    """
    try:
        # Create incident record in database
        incident = IncidentRepository.create(
            title=req.title,
            description=req.description,
            service=req.service,
            source=req.source or "manual",
            external_id=req.external_id,
            status="OPEN"
        )
        incident_id = incident["id"]

        # Record initial incident creation event in audit trail
        IncidentEventRepository.create(
            incident_id=incident_id,
            event_type="INCIDENT_CREATED",
            message=f"Incident opened: {req.title}",
            metadata={"service": req.service, "source": req.source or "manual"}
        )

        logger.info(f"Received new incident {incident_id}: '{req.title}' for service '{req.service}'")

        # Run LangGraph autonomous triage workflow
        # The graph executes sequentially up to completion or until an approval interrupt
        workflow_result = run_incident_workflow(
            incident_id=incident_id,
            title=req.title,
            description=req.description,
            service=req.service,
            source=req.source or "manual",
            external_id=req.external_id
        )

        # Retrieve current status after execution
        updated = IncidentRepository.get(incident_id) or incident
        current_status = updated.get("status", "INVESTIGATING")

        return IncidentCreateResponse(
            incident_id=incident_id,
            status=IncidentStatus(current_status)
        )
    except Exception as e:
        logger.error(f"Error initiating incident triage: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate autonomous incident triage workflow."
        )


@router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    summary="Retrieve incident status and diagnosis details"
)
def get_incident(incident_id: str):
    """Fetch current diagnosis, risk score, recommended action, and approval requirements."""
    incident = IncidentRepository.get(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found."
        )

    # Determine pending action details if awaiting approval
    pending_action = None
    action_name = incident.get("recommended_action")
    action_risk_str = incident.get("severity") or "HIGH"
    
    if action_name and incident.get("status") == "AWAITING_APPROVAL":
        policy = get_action_policy(action_name) or {}
        risk_enum = policy.get("risk", ActionRiskLevel.HIGH)
        pending_action = PendingAction(
            name=action_name,
            service=incident["service"],
            risk=risk_enum,
            reason=incident.get("root_cause_hypothesis")
        )

    approval_required = incident.get("status") == "AWAITING_APPROVAL" or (
        bool(action_name) and get_action_policy(action_name or "").get("requires_approval", False)
    )

    return IncidentDetailResponse(
        id=incident["id"],
        external_id=incident.get("external_id"),
        title=incident["title"],
        description=incident["description"],
        service=incident["service"],
        severity=incident.get("severity"),
        status=IncidentStatus(incident["status"]),
        root_cause_hypothesis=incident.get("root_cause_hypothesis"),
        confidence=incident.get("confidence"),
        recommended_action=action_name,
        action_risk=get_action_policy(action_name or "").get("risk") if action_name else None,
        approval_required=approval_required,
        pending_action=pending_action,
        created_at=incident["created_at"],
        updated_at=incident["updated_at"],
        resolved_at=incident.get("resolved_at")
    )


@router.get(
    "/{incident_id}/events",
    response_model=List[IncidentEventResponse],
    summary="Retrieve complete audit log of incident events"
)
def get_incident_events(incident_id: str):
    """Retrieve chronological audit trail of all state transitions and telemetry events."""
    incident = IncidentRepository.get(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found."
        )

    events = IncidentEventRepository.get_by_incident(incident_id)
    return [
        IncidentEventResponse(
            id=e["id"],
            incident_id=e["incident_id"],
            event_type=e["event_type"],
            message=e["message"],
            metadata=e["metadata"] if isinstance(e["metadata"], dict) else {},
            created_at=e["created_at"]
        )
        for e in events
    ]
