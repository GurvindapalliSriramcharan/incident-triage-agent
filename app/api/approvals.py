import logging
from fastapi import APIRouter, HTTPException, status

from app.agent.graph import resume_incident_workflow
from app.db.repositories import IncidentRepository
from app.schemas.incident import (
    ApprovalRequest,
    IncidentDetailResponse,
    IncidentStatus,
    PendingAction,
    RejectionRequest,
)
from app.tools.actions import get_action_policy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["approvals"])


@router.post(
    "/{incident_id}/approve",
    response_model=IncidentDetailResponse,
    summary="Approve a pending high-risk remediation action"
)
def approve_action(incident_id: str, req: ApprovalRequest):
    """
    Approve proposed high-risk action.
    Resumes LangGraph execution from checkpoint, executes remediation,
    verifies service health, and transitions to RESOLVED (or ESCALATED if verification fails).
    """
    incident = IncidentRepository.get(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found."
        )

    current_status = incident.get("status")
    # Idempotency and state validation
    if current_status in ("RESOLVED", "REJECTED", "ESCALATED", "FAILED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Incident is already in terminal state '{current_status}'. Action cannot be executed again."
        )

    if current_status != "AWAITING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incident is in '{current_status}' state, not awaiting human approval."
        )

    try:
        logger.info(f"Human approval received for incident {incident_id}: {req.reason}")
        resume_incident_workflow(
            incident_id=incident_id,
            approved=True,
            reason=req.reason or "Approved by on-call engineer"
        )
    except Exception as e:
        logger.error(f"Error resuming incident workflow upon approval: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resume incident workflow for action execution."
        )

    updated = IncidentRepository.get(incident_id)
    action_name = updated.get("recommended_action")

    return IncidentDetailResponse(
        id=updated["id"],
        external_id=updated.get("external_id"),
        title=updated["title"],
        description=updated["description"],
        service=updated["service"],
        severity=updated.get("severity"),
        status=IncidentStatus(updated["status"]),
        root_cause_hypothesis=updated.get("root_cause_hypothesis"),
        confidence=updated.get("confidence"),
        recommended_action=action_name,
        action_risk=get_action_policy(action_name or "").get("risk") if action_name else None,
        approval_required=False,
        pending_action=None,
        created_at=updated["created_at"],
        updated_at=updated["updated_at"],
        resolved_at=updated.get("resolved_at")
    )


@router.post(
    "/{incident_id}/reject",
    response_model=IncidentDetailResponse,
    summary="Reject a pending high-risk remediation action"
)
def reject_action(incident_id: str, req: RejectionRequest):
    """
    Reject proposed action.
    Resumes LangGraph execution from checkpoint, bypasses execution,
    logs rejection audit event, and transitions incident to REJECTED.
    """
    incident = IncidentRepository.get(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found."
        )

    current_status = incident.get("status")
    # Idempotency and state validation
    if current_status in ("RESOLVED", "REJECTED", "ESCALATED", "FAILED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Incident is already in terminal state '{current_status}'. Cannot reject."
        )

    if current_status != "AWAITING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incident is in '{current_status}' state, not awaiting human approval."
        )

    try:
        logger.info(f"Human rejection received for incident {incident_id}: {req.reason}")
        resume_incident_workflow(
            incident_id=incident_id,
            approved=False,
            reason=req.reason or "Rejected by human operator"
        )
    except Exception as e:
        logger.error(f"Error resuming incident workflow upon rejection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resume incident workflow for rejection."
        )

    updated = IncidentRepository.get(incident_id)
    action_name = updated.get("recommended_action")

    return IncidentDetailResponse(
        id=updated["id"],
        external_id=updated.get("external_id"),
        title=updated["title"],
        description=updated["description"],
        service=updated["service"],
        severity=updated.get("severity"),
        status=IncidentStatus(updated["status"]),
        root_cause_hypothesis=updated.get("root_cause_hypothesis"),
        confidence=updated.get("confidence"),
        recommended_action=action_name,
        action_risk=get_action_policy(action_name or "").get("risk") if action_name else None,
        approval_required=False,
        pending_action=None,
        created_at=updated["created_at"],
        updated_at=updated["updated_at"],
        resolved_at=updated.get("resolved_at")
    )
