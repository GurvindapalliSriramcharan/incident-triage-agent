from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    REMEDIATING = "REMEDIATING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Brief summary of the incident")
    description: str = Field(..., min_length=5, description="Detailed incident description and symptoms")
    service: str = Field(..., min_length=2, max_length=100, description="Affected target service (e.g. auth, database, payments)")
    source: Optional[str] = Field("manual", description="Alert source (e.g. datadog, pagerduty, manual)")
    external_id: Optional[str] = Field(None, description="External incident/ticket ID")


class IncidentCreateResponse(BaseModel):
    incident_id: str
    status: IncidentStatus


class PendingAction(BaseModel):
    name: str
    service: str
    risk: ActionRiskLevel
    reason: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


class IncidentDetailResponse(BaseModel):
    id: str
    external_id: Optional[str] = None
    title: str
    description: str
    service: str
    severity: Optional[str] = None
    status: IncidentStatus
    root_cause_hypothesis: Optional[str] = None
    confidence: Optional[float] = None
    recommended_action: Optional[str] = None
    action_risk: Optional[str] = None
    approval_required: bool = False
    pending_action: Optional[PendingAction] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None


class ApprovalRequest(BaseModel):
    approved: bool = Field(True, description="Approval decision")
    reason: Optional[str] = Field(None, description="Reason for approving the remediation action")


class RejectionRequest(BaseModel):
    reason: Optional[str] = Field("Rejected by human operator", description="Reason for rejecting the proposed action")


class IncidentEventResponse(BaseModel):
    id: str
    incident_id: str
    event_type: str
    message: str
    metadata: Dict[str, Any]
    created_at: datetime


class HealthCheckResponse(BaseModel):
    status: str
    environment: str
    database_connected: bool
    gemini_configured: bool
    version: str = "1.0.0"
