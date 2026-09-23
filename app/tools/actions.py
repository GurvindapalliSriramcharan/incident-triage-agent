import logging
from typing import Any, Dict, Optional
from app.schemas.incident import ActionRiskLevel

logger = logging.getLogger(__name__)

# Registry defining all valid actions, their risk levels, and whether human approval is mandatory
ACTION_REGISTRY: Dict[str, Dict[str, Any]] = {
    "read_health": {
        "risk": ActionRiskLevel.LOW,
        "requires_approval": False,
        "description": "Inspect service health endpoints and metrics."
    },
    "search_runbook": {
        "risk": ActionRiskLevel.LOW,
        "requires_approval": False,
        "description": "Search vector database for internal remediation runbooks."
    },
    "clear_cache": {
        "risk": ActionRiskLevel.LOW,
        "requires_approval": False,
        "description": "Evict expired tokens or temporary cache keys."
    },
    "create_escalation_ticket": {
        "risk": ActionRiskLevel.MEDIUM,
        "requires_approval": False,
        "description": "Open an escalation ticket in PagerDuty / Jira."
    },
    "restart_service": {
        "risk": ActionRiskLevel.HIGH,
        "requires_approval": True,
        "description": "Gracefully restart affected service replicas or pods."
    },
    "terminate_idle_transaction": {
        "risk": ActionRiskLevel.HIGH,
        "requires_approval": True,
        "description": "Terminate idle-in-transaction connections holding database locks."
    },
    "failover_database": {
        "risk": ActionRiskLevel.CRITICAL,
        "requires_approval": True,
        "description": "Promote read replica to primary database during critical failure."
    },
    "switch_payment_provider": {
        "risk": ActionRiskLevel.CRITICAL,
        "requires_approval": True,
        "description": "Reroute live transaction traffic to backup payment processor."
    }
}


def get_action_policy(action_name: str) -> Optional[Dict[str, Any]]:
    """Look up policy metadata for a given action name."""
    if not action_name:
        return None
    normalized = action_name.strip().lower()
    return ACTION_REGISTRY.get(normalized)


def is_action_allowed(action_name: str) -> bool:
    """Validate whether an action is in the approved registry."""
    return get_action_policy(action_name) is not None


def requires_human_approval(action_name: str) -> bool:
    """Determine whether the specified action requires human approval before execution."""
    policy = get_action_policy(action_name)
    if not policy:
        # Unknown actions are unsafe by default
        return True
    return policy.get("requires_approval", True)


def execute_simulated_action(
    action_name: str,
    service: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Safely execute a registered action in simulation mode.
    Guarantees no arbitrary code/shell commands can run.
    """
    normalized_action = (action_name or "").strip().lower()
    policy = get_action_policy(normalized_action)

    if not policy:
        logger.error(f"Attempted to execute unregistered or illegal action: {action_name}")
        return {
            "success": False,
            "action": action_name,
            "service": service,
            "error": f"Action '{action_name}' is not in the approved safety registry.",
            "is_simulated": True
        }

    logger.info(f"[SIMULATION] Executing {normalized_action} on {service} with params={params}")

    if normalized_action == "restart_service":
        return {
            "success": True,
            "action": "restart_service",
            "service": service,
            "message": f"Simulated rolling restart of '{service}' replicas completed. New pods healthy and ready.",
            "stabilized": True,
            "is_simulated": True
        }
    elif normalized_action == "clear_cache":
        return {
            "success": True,
            "action": "clear_cache",
            "service": service,
            "message": f"Simulated cache eviction on '{service}' redis cluster completed. 1,280 expired keys removed.",
            "stabilized": True,
            "is_simulated": True
        }
    elif normalized_action == "terminate_idle_transaction":
        return {
            "success": True,
            "action": "terminate_idle_transaction",
            "service": service,
            "message": f"Simulated termination of 3 idle transactions on '{service}'. Locks released.",
            "stabilized": True,
            "is_simulated": True
        }
    elif normalized_action == "failover_database":
        return {
            "success": True,
            "action": "failover_database",
            "service": service,
            "message": f"Simulated database failover completed. Standby promoted to primary cluster.",
            "stabilized": True,
            "is_simulated": True
        }
    elif normalized_action == "switch_payment_provider":
        return {
            "success": True,
            "action": "switch_payment_provider",
            "service": service,
            "message": f"Simulated traffic shift to backup payment provider completed. 100% traffic shifted.",
            "stabilized": True,
            "is_simulated": True
        }
    elif normalized_action == "create_escalation_ticket":
        ticket_id = f"INC-{service.upper()}-8821"
        return {
            "success": True,
            "action": "create_escalation_ticket",
            "service": service,
            "ticket_id": ticket_id,
            "message": f"Simulated escalation ticket {ticket_id} created and dispatched to on-call paging group.",
            "stabilized": False,
            "is_simulated": True
        }
    else:
        return {
            "success": True,
            "action": normalized_action,
            "service": service,
            "message": f"Simulated execution of {normalized_action} completed.",
            "stabilized": True,
            "is_simulated": True
        }
