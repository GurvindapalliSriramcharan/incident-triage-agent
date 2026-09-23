from typing import Literal
from pydantic import BaseModel, Field

INCIDENT_ANALYSIS_SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) and Autonomous Incident Triage Agent.

Your mission:
Analyze an incoming incident, investigate the evidence collected from service health telemetry, recent application logs, and retrieved internal runbooks, and determine:
1. Incident Severity (LOW, MEDIUM, HIGH, CRITICAL)
2. Most likely Root Cause Hypothesis based on the collected evidence
3. Confidence level (0.0 to 1.0)
4. Recommended remediation action chosen STRICTLY from the allowed action registry
5. Risk rating of the recommended action (LOW, MEDIUM, HIGH, CRITICAL)
6. Clear reasoning summary justifying the recommendation

ALLOWED ACTION REGISTRY (DO NOT INVENT ACTIONS):
- clear_cache (Risk: LOW) -> Flush expired keys or caches
- create_escalation_ticket (Risk: MEDIUM) -> Dispatch to on-call engineers when no safe automated remediation exists
- restart_service (Risk: HIGH) -> Restart degraded replicas/pods (requires human approval)
- terminate_idle_transaction (Risk: HIGH) -> Terminate blocking idle database transactions (requires human approval)
- failover_database (Risk: CRITICAL) -> Failover database cluster to standby replica (requires human approval)
- switch_payment_provider (Risk: CRITICAL) -> Reroute live financial transactions to backup provider (requires human approval)

Always select an action from the registry that best addresses the diagnosed root cause based on the internal runbooks.
"""


class IncidentAnalysisOutput(BaseModel):
    """Structured reasoning output produced by Gemini LLM."""
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        ...,
        description="Overall incident severity rating."
    )
    root_cause_hypothesis: str = Field(
        ...,
        description="Detailed hypothesis of the root cause substantiated by health and log evidence."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this diagnosis (between 0.0 and 1.0)."
    )
    recommended_action: Literal[
        "clear_cache",
        "restart_service",
        "terminate_idle_transaction",
        "failover_database",
        "switch_payment_provider",
        "create_escalation_ticket"
    ] = Field(
        ...,
        description="Recommended action strictly selected from the allowed registry."
    )
    action_risk: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        ...,
        description="Risk level associated with executing this remediation action."
    )
    reasoning_summary: str = Field(
        ...,
        description="Concise rationale explaining the diagnosis and why this action was selected."
    )
