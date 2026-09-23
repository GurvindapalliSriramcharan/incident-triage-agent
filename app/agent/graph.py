import logging
from typing import Any, Dict, Optional
import psycopg
from psycopg.rows import dict_row
import psycopg_pool
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agent.nodes import (
    analyze_incident_node,
    collect_health_node,
    collect_logs_node,
    complete_resolved_node,
    escalate_node,
    execute_action_node,
    handle_rejection_node,
    load_incident_node,
    propose_action_node,
    request_approval_node,
    retrieve_runbooks_node,
    triage_incident_node,
    verify_resolution_node,
)
from app.agent.routing import (
    route_approval_decision,
    route_risk_gate,
    route_verification,
)
from app.agent.state import IncidentState
from app.config import settings

logger = logging.getLogger(__name__)

_memory_saver = MemorySaver()
_postgres_saver: Optional[PostgresSaver] = None
_checkpointer_pool: Optional[psycopg_pool.ConnectionPool] = None
_compiled_graph = None


def get_checkpointer() -> BaseCheckpointSaver:
    """
    Get or initialize the persistent checkpointer.
    Uses PostgreSQL-backed PostgresSaver backed by a ConnectionPool with prepare_threshold=None
    for complete compatibility with Supabase, PgBouncer, and Render.
    Falls back to MemorySaver for testing or offline execution.
    """
    global _postgres_saver, _checkpointer_pool
    if _postgres_saver is not None:
        return _postgres_saver

    db_url = settings.DATABASE_URL
    if db_url:
        try:
            import psycopg_pool
            _checkpointer_pool = psycopg_pool.ConnectionPool(
                conninfo=db_url,
                min_size=1,
                max_size=10,
                timeout=10.0,
                open=True,
                kwargs={
                    "row_factory": dict_row,
                    "autocommit": True,
                    "prepare_threshold": None
                }
            )
            saver = PostgresSaver(_checkpointer_pool)
            saver.setup()
            _postgres_saver = saver
            logger.info("LangGraph persistent PostgresSaver initialized successfully with ConnectionPool and prepare_threshold=None.")
            return _postgres_saver
        except Exception as e:
            logger.warning(f"Failed to initialize PostgresSaver: {e}. Falling back to MemorySaver.")
            return _memory_saver

    return _memory_saver


def build_incident_graph(checkpointer: Optional[BaseCheckpointSaver] = None):
    """Construct and compile the incident triage StateGraph workflow."""
    saver = checkpointer or get_checkpointer()

    builder = StateGraph(IncidentState)

    # Register workflow nodes
    builder.add_node("load_incident", load_incident_node)
    builder.add_node("triage_incident", triage_incident_node)
    builder.add_node("collect_health", collect_health_node)
    builder.add_node("collect_logs", collect_logs_node)
    builder.add_node("retrieve_runbooks", retrieve_runbooks_node)
    builder.add_node("analyze_incident", analyze_incident_node)
    builder.add_node("propose_action", propose_action_node)
    builder.add_node("request_approval", request_approval_node)
    builder.add_node("handle_rejection", handle_rejection_node)
    builder.add_node("execute_action", execute_action_node)
    builder.add_node("verify_resolution", verify_resolution_node)
    builder.add_node("complete_resolved", complete_resolved_node)
    builder.add_node("escalate", escalate_node)

    # Define sequential edges
    builder.set_entry_point("load_incident")
    builder.add_edge("load_incident", "triage_incident")
    builder.add_edge("triage_incident", "collect_health")
    builder.add_edge("collect_health", "collect_logs")
    builder.add_edge("collect_logs", "retrieve_runbooks")
    builder.add_edge("retrieve_runbooks", "analyze_incident")
    builder.add_edge("analyze_incident", "propose_action")

    # Risk policy gate: low risk auto-executes, high/critical risk pauses for approval
    builder.add_conditional_edges(
        "propose_action",
        route_risk_gate,
        {
            "request_approval": "request_approval",
            "execute_action": "execute_action"
        }
    )

    # Human-in-the-loop decision routing
    builder.add_conditional_edges(
        "request_approval",
        route_approval_decision,
        {
            "execute_action": "execute_action",
            "handle_rejection": "handle_rejection"
        }
    )

    # Post-action verification
    builder.add_edge("execute_action", "verify_resolution")

    # Verification outcome routing
    builder.add_conditional_edges(
        "verify_resolution",
        route_verification,
        {
            "complete_resolved": "complete_resolved",
            "escalate": "escalate"
        }
    )

    # Terminal edges
    builder.add_edge("complete_resolved", END)
    builder.add_edge("handle_rejection", END)
    builder.add_edge("escalate", END)

    return builder.compile(checkpointer=saver)


def get_compiled_graph():
    """Get or build the compiled LangGraph singleton."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_incident_graph()
    return _compiled_graph


def run_incident_workflow(
    incident_id: str,
    title: str,
    description: str,
    service: str,
    source: str = "manual",
    external_id: Optional[str] = None
) -> Dict[str, Any]:
    """Execute the incident triage workflow up to completion or human interrupt."""
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": incident_id}}

    initial_state: IncidentState = {
        "incident_id": incident_id,
        "external_id": external_id,
        "title": title,
        "description": description,
        "service": service,
        "source": source,
        "severity": None,
        "status": "OPEN",
        "evidence": {},
        "health_results": {},
        "log_results": [],
        "retrieved_runbooks": [],
        "root_cause_hypothesis": None,
        "confidence": None,
        "reasoning_summary": None,
        "recommended_action": None,
        "action_risk": None,
        "approval_required": False,
        "approval_status": None,
        "approval_reason": None,
        "action_result": None,
        "verification_result": None,
        "final_status": "OPEN",
        "error": None
    }

    result = graph.invoke(initial_state, config=config)
    return result


def resume_incident_workflow(
    incident_id: str,
    approved: bool,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """Resume an interrupted incident workflow with human operator decision."""
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": incident_id}}

    resume_payload = {
        "approved": approved,
        "reason": reason or ("Approved by operator" if approved else "Rejected by operator")
    }

    result = graph.invoke(Command(resume=resume_payload), config=config)
    return result
