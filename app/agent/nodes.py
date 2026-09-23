import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict
from langgraph.types import interrupt

from app.agent.prompts import INCIDENT_ANALYSIS_SYSTEM_PROMPT, IncidentAnalysisOutput
from app.agent.state import IncidentState
from app.config import settings
from app.db.repositories import IncidentEventRepository, IncidentRepository
from app.tools.actions import (
    execute_simulated_action,
    get_action_policy,
    is_action_allowed,
    requires_human_approval,
)
from app.tools.health import check_service_health
from app.tools.logs import get_service_logs
from app.tools.rag import search_runbooks

logger = logging.getLogger(__name__)


def _log_step(incident_id: str, node: str, message: str):
    logger.info(f"[{incident_id}] [{node}] {message}")


def load_incident_node(state: IncidentState) -> Dict[str, Any]:
    """Node: Load or verify initial incident in database and register creation event."""
    inc_id = state["incident_id"]
    _log_step(inc_id, "load", f"Loading incident '{state['title']}' for service '{state['service']}'")

    existing = IncidentRepository.get(inc_id)
    if not existing:
        IncidentRepository.create(
            title=state["title"],
            description=state["description"],
            service=state["service"],
            source=state.get("source", "manual"),
            external_id=state.get("external_id"),
            status="OPEN",
            incident_id=inc_id
        )
        IncidentEventRepository.create(
            incident_id=inc_id,
            event_type="INCIDENT_CREATED",
            message=f"Incident opened: {state['title']}",
            metadata={"service": state["service"], "source": state.get("source", "manual")}
        )

    return {"status": "OPEN"}


def triage_incident_node(state: IncidentState) -> Dict[str, Any]:
    """Node: Set incident to INVESTIGATING status."""
    inc_id = state["incident_id"]
    _log_step(inc_id, "triage", "Starting initial triage and investigation")

    IncidentRepository.update(inc_id, {"status": "INVESTIGATING"})
    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="INVESTIGATING",
        message="Incident status updated to INVESTIGATING. Beginning evidence collection.",
        metadata={"service": state["service"]}
    )
    return {"status": "INVESTIGATING"}


def collect_health_node(state: IncidentState) -> Dict[str, Any]:
    """Node: Collect telemetry health check for the target service."""
    inc_id = state["incident_id"]
    health = check_service_health(state["service"])
    _log_step(inc_id, "health", f"{state['service']} status = {health.get('status')}")

    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="HEALTH_CHECK",
        message=f"Service health check for {state['service']}: status is {health.get('status')}",
        metadata=health
    )
    return {
        "health_results": health,
        "evidence": {**state.get("evidence", {}), "health": health}
    }


def collect_logs_node(state: IncidentState) -> Dict[str, Any]:
    """Node: Collect recent error logs for the affected service."""
    inc_id = state["incident_id"]
    logs = get_service_logs(state["service"], limit=5)
    _log_step(inc_id, "logs", f"Collected {len(logs)} log entries for {state['service']}")

    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="LOGS_COLLECTED",
        message=f"Collected {len(logs)} telemetry log lines for {state['service']}",
        metadata={"log_count": len(logs), "samples": logs[:3]}
    )
    return {
        "log_results": logs,
        "evidence": {**state.get("evidence", {}), "logs": logs}
    }


def retrieve_runbooks_node(state: IncidentState) -> Dict[str, Any]:
    """Node: Semantic RAG search for relevant internal runbooks."""
    inc_id = state["incident_id"]
    query = f"{state['title']} {state['description']}"
    runbooks = search_runbooks(query, service=state["service"], top_k=settings.MAX_RAG_RESULTS)
    _log_step(inc_id, "rag", f"Retrieved {len(runbooks)} relevant runbook chunks for {state['service']}")

    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="RAG_SEARCH",
        message=f"Retrieved {len(runbooks)} runbook sections matching symptoms",
        metadata={
            "query": query,
            "results": [
                {
                    "source": r.get("metadata", {}).get("source"),
                    "similarity": r.get("similarity"),
                    "title": r.get("metadata", {}).get("title")
                }
                for r in runbooks
            ]
        }
    )
    return {
        "retrieved_runbooks": runbooks,
        "evidence": {**state.get("evidence", {}), "runbooks": runbooks}
    }


def analyze_incident_node(state: IncidentState) -> Dict[str, Any]:
    """
    Node: Reason over evidence using Gemini LLM (with deterministic offline fallback).
    Produces structured output containing severity, root cause, confidence, and recommended action.
    """
    inc_id = state["incident_id"]
    _log_step(inc_id, "analysis", "Synthesizing evidence and generating root cause hypothesis")

    # Attempt LLM structured inference if API key is provided
    analysis: IncidentAnalysisOutput = None
    if settings.GEMINI_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import SystemMessage, HumanMessage

            llm = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                google_api_key=settings.GEMINI_API_KEY
            )
            structured_llm = llm.with_structured_output(IncidentAnalysisOutput)

            evidence_summary = {
                "incident": {
                    "title": state["title"],
                    "description": state["description"],
                    "service": state["service"]
                },
                "health": state.get("health_results", {}),
                "logs": state.get("log_results", []),
                "runbooks": [
                    {
                        "source": r.get("metadata", {}).get("source"),
                        "content": r.get("content")
                    }
                    for r in state.get("retrieved_runbooks", [])
                ]
            }

            response = structured_llm.invoke([
                SystemMessage(content=INCIDENT_ANALYSIS_SYSTEM_PROMPT),
                HumanMessage(content=f"Please analyze the following incident evidence:\n{json.dumps(evidence_summary, indent=2)}")
            ])
            if isinstance(response, IncidentAnalysisOutput):
                analysis = response
        except Exception as e:
            logger.warning(f"Gemini LLM inference encountered error: {e}. Utilizing deterministic fallback analysis.")

    # Resilient deterministic fallback analysis for testing or offline environments
    if analysis is None:
        service = state["service"].lower()
        health = state.get("health_results", {})
        if service == "auth" or "timeout" in state["title"].lower():
            analysis = IncidentAnalysisOutput(
                severity="HIGH",
                root_cause_hypothesis="Auth replicas are experiencing thread contention, garbage collection pauses, and Redis read lock wait timeouts.",
                confidence=0.88,
                recommended_action="restart_service",
                action_risk="HIGH",
                reasoning_summary="Auth service health is DEGRADED with 18.5% error rate on token endpoints. Runbook recommends restarting degraded replicas."
            )
        elif service == "database" or "latency" in state["title"].lower():
            analysis = IncidentAnalysisOutput(
                severity="HIGH",
                root_cause_hypothesis="Long-running idle-in-transaction connections are holding locks and causing query latency spikes.",
                confidence=0.85,
                recommended_action="terminate_idle_transaction",
                action_risk="HIGH",
                reasoning_summary="Idle transactions detected in activity logs. Runbook recommends terminating idle sessions."
            )
        elif service == "payments":
            analysis = IncidentAnalysisOutput(
                severity="CRITICAL",
                root_cause_hypothesis="Upstream primary payment gateway is experiencing elevated 504 timeouts.",
                confidence=0.82,
                recommended_action="switch_payment_provider",
                action_risk="CRITICAL",
                reasoning_summary="Primary gateway errors exceed threshold. Runbook recommends failover to backup provider."
            )
        else:
            analysis = IncidentAnalysisOutput(
                severity="MEDIUM",
                root_cause_hypothesis=f"Anomalous telemetry detected on {service}.",
                confidence=0.70,
                recommended_action="create_escalation_ticket",
                action_risk="MEDIUM",
                reasoning_summary=f"No automated remediation runbook matched for {service}; escalating to on-call."
            )

    _log_step(inc_id, "analysis", f"Severity = {analysis.severity}, Action = {analysis.recommended_action} (Risk: {analysis.action_risk})")

    # Update database with diagnosis
    IncidentRepository.update(inc_id, {
        "severity": analysis.severity,
        "root_cause_hypothesis": analysis.root_cause_hypothesis,
        "confidence": analysis.confidence,
        "recommended_action": analysis.recommended_action
    })

    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="LLM_ANALYSIS",
        message=f"Root cause hypothesis: {analysis.root_cause_hypothesis}",
        metadata={
            "severity": analysis.severity,
            "confidence": analysis.confidence,
            "recommended_action": analysis.recommended_action,
            "action_risk": analysis.action_risk,
            "reasoning_summary": analysis.reasoning_summary
        }
    )

    return {
        "severity": analysis.severity,
        "root_cause_hypothesis": analysis.root_cause_hypothesis,
        "confidence": analysis.confidence,
        "recommended_action": analysis.recommended_action,
        "action_risk": analysis.action_risk,
        "reasoning_summary": analysis.reasoning_summary
    }


def propose_action_node(state: IncidentState) -> Dict[str, Any]:
    """Node: Validate proposed action against policy and determine risk gating."""
    inc_id = state["incident_id"]
    action_name = state.get("recommended_action")

    if not is_action_allowed(action_name):
        _log_step(inc_id, "policy", f"Action '{action_name}' rejected by safety policy: not allowed.")
        return {
            "recommended_action": "create_escalation_ticket",
            "action_risk": "MEDIUM",
            "approval_required": False
        }

    policy = get_action_policy(action_name)
    requires_approval = policy.get("requires_approval", True)
    risk_level = policy.get("risk", "HIGH")
    if hasattr(risk_level, "value"):
        risk_level = risk_level.value
    else:
        risk_level = str(risk_level)

    _log_step(inc_id, "policy", f"Action '{action_name}' evaluated. Risk: {risk_level}, Requires Approval: {requires_approval}")

    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="ACTION_PROPOSED",
        message=f"Proposed remediation action: {action_name} (Risk: {risk_level})",
        metadata={
            "action": action_name,
            "risk": risk_level,
            "requires_approval": requires_approval
        }
    )

    return {
        "action_risk": risk_level,
        "approval_required": requires_approval
    }


def request_approval_node(state: IncidentState) -> Dict[str, Any]:
    """
    Node: Pause execution for human approval on high-risk actions.
    Uses LangGraph interrupt() and resumes with human decision.
    """
    inc_id = state["incident_id"]
    _log_step(inc_id, "approval", f"Awaiting human approval for action '{state['recommended_action']}'")

    # Update incident state in DB to AWAITING_APPROVAL
    IncidentRepository.update(inc_id, {"status": "AWAITING_APPROVAL"})

    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="APPROVAL_REQUESTED",
        message=f"Action '{state['recommended_action']}' on service '{state['service']}' requires human approval.",
        metadata={
            "action": state["recommended_action"],
            "risk": state["action_risk"],
            "service": state["service"],
            "reasoning": state.get("reasoning_summary")
        }
    )

    # LangGraph HITL interrupt: execution pauses here until resumed with Command(resume=...)
    human_input = interrupt({
        "incident_id": inc_id,
        "action": state["recommended_action"],
        "service": state["service"],
        "risk": state["action_risk"],
        "reasoning": state.get("reasoning_summary")
    })

    # Resumed execution
    approved = False
    reason = "No reason provided"
    if isinstance(human_input, dict):
        approved = bool(human_input.get("approved", False))
        reason = human_input.get("reason", reason)

    decision_status = "APPROVED" if approved else "REJECTED"
    _log_step(inc_id, "approval", f"Human decision received: {decision_status} (Reason: {reason})")

    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="ACTION_APPROVED" if approved else "ACTION_REJECTED",
        message=f"Human operator {decision_status.lower()} action '{state['recommended_action']}': {reason}",
        metadata={"approved": approved, "reason": reason}
    )

    return {
        "approval_status": decision_status,
        "approval_reason": reason
    }


def handle_rejection_node(state: IncidentState) -> Dict[str, Any]:
    """Node: Handle rejection by human operator. Aborts execution and marks incident REJECTED."""
    inc_id = state["incident_id"]
    _log_step(inc_id, "reject", "Action rejected by operator. Transitioning incident to REJECTED.")

    IncidentRepository.update(inc_id, {"status": "REJECTED"})
    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="REJECTED",
        message="Incident closed as REJECTED after operator declined proposed remediation.",
        metadata={"reason": state.get("approval_reason")}
    )
    return {
        "status": "REJECTED",
        "final_status": "REJECTED"
    }


def execute_action_node(state: IncidentState) -> Dict[str, Any]:
    """Node: Execute the verified remediation action safely via the action registry."""
    inc_id = state["incident_id"]
    action_name = state["recommended_action"]
    service = state["service"]

    _log_step(inc_id, "execute", f"Executing remediation action '{action_name}' on '{service}'")

    IncidentRepository.update(inc_id, {"status": "REMEDIATING"})
    action_res = execute_simulated_action(action_name, service)

    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="ACTION_EXECUTED",
        message=f"Executed simulated action {action_name}: {action_res.get('message')}",
        metadata=action_res
    )

    return {
        "status": "REMEDIATING",
        "action_result": action_res
    }


def verify_resolution_node(state: IncidentState) -> Dict[str, Any]:
    """Node: Verify whether the service has stabilized after remediation."""
    inc_id = state["incident_id"]
    service = state["service"]
    action_res = state.get("action_result", {})
    action_stabilized = action_res.get("stabilized", False)

    _log_step(inc_id, "verify", f"Verifying service health post-remediation for '{service}'")
    IncidentRepository.update(inc_id, {"status": "VERIFYING"})

    # Check post-remediation health (simulating stabilized metrics if action was successful)
    override = "HEALTHY" if action_stabilized else None
    post_health = check_service_health(service, override_status=override)

    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="VERIFICATION",
        message=f"Post-remediation health check: status is {post_health.get('status')}",
        metadata=post_health
    )

    is_healthy = post_health.get("status") == "HEALTHY"
    final_status = "RESOLVED" if is_healthy else "FAILED"

    return {
        "status": final_status,
        "verification_result": post_health,
        "final_status": final_status
    }


def complete_resolved_node(state: IncidentState) -> Dict[str, Any]:
    """Node: Finalize incident resolution and mark RESOLVED."""
    inc_id = state["incident_id"]
    now = datetime.now(timezone.utc)
    _log_step(inc_id, "resolve", "Incident successfully resolved and verified.")

    IncidentRepository.update(inc_id, {
        "status": "RESOLVED",
        "resolved_at": now
    })

    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="RESOLVED",
        message="Incident marked as RESOLVED following successful remediation and verification.",
        metadata={"resolved_at": now.isoformat()}
    )
    return {"status": "RESOLVED", "final_status": "RESOLVED"}


def escalate_node(state: IncidentState) -> Dict[str, Any]:
    """Node: Escalate incident to on-call engineers when remediation failed or rejected."""
    inc_id = state["incident_id"]
    _log_step(inc_id, "escalate", "Remediation failed or rejected. Escalating to engineering.")

    ticket_res = execute_simulated_action("create_escalation_ticket", state["service"])

    IncidentRepository.update(inc_id, {"status": "ESCALATED"})
    IncidentEventRepository.create(
        incident_id=inc_id,
        event_type="ESCALATED",
        message=f"Incident escalated to human on-call tier: {ticket_res.get('message')}",
        metadata=ticket_res
    )
    return {"status": "ESCALATED", "final_status": "ESCALATED"}
