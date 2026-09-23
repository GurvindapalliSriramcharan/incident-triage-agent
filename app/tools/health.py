import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Known simulated service statuses for the initial incident scenarios
DEFAULT_SERVICE_PROFILES: Dict[str, Dict[str, Any]] = {
    "auth": {
        "status": "DEGRADED",
        "latency_ms": 1240,
        "error_rate_pct": 18.5,
        "active_replicas": "3/3",
        "cpu_usage_pct": 89.2,
        "memory_usage_pct": 74.0,
        "details": "High HTTP 504 Gateway Timeout rate on /oauth/token and token validation endpoints.",
        "dependencies": {
            "redis_cache": "DEGRADED (high connection latency)",
            "user_db": "HEALTHY"
        }
    },
    "database": {
        "status": "HEALTHY",
        "latency_ms": 14,
        "error_rate_pct": 0.05,
        "active_replicas": "2/2",
        "cpu_usage_pct": 42.1,
        "memory_usage_pct": 58.6,
        "details": "PostgreSQL cluster operating within normal parameters.",
        "dependencies": {
            "primary_storage": "HEALTHY",
            "wal_archiver": "HEALTHY"
        }
    },
    "payments": {
        "status": "HEALTHY",
        "latency_ms": 65,
        "error_rate_pct": 0.1,
        "active_replicas": "4/4",
        "cpu_usage_pct": 36.5,
        "memory_usage_pct": 49.8,
        "details": "Payment gateway integrations responsive and queue size is nominal.",
        "dependencies": {
            "external_stripe_api": "HEALTHY",
            "payment_db": "HEALTHY"
        }
    }
}


def check_service_health(service: str, override_status: Optional[str] = None) -> Dict[str, Any]:
    """
    Check health metrics for a given service.
    Clearly simulated infrastructure tool for incident triage MVP.
    """
    service_normalized = (service or "").strip().lower()
    profile = DEFAULT_SERVICE_PROFILES.get(service_normalized)

    if profile is None:
        logger.warning(f"Health check requested for unknown service: {service}")
        return {
            "service": service,
            "status": "UNKNOWN",
            "latency_ms": -1,
            "error_rate_pct": -1.0,
            "active_replicas": "0/0",
            "details": f"Service '{service}' is not recognized in service catalog or telemetry mesh.",
            "is_simulated": True
        }

    # Return profile with optional override (e.g. after action stabilization)
    result = {
        "service": service_normalized,
        "status": override_status or profile["status"],
        "latency_ms": 25 if override_status == "HEALTHY" else profile["latency_ms"],
        "error_rate_pct": 0.0 if override_status == "HEALTHY" else profile["error_rate_pct"],
        "active_replicas": profile["active_replicas"],
        "cpu_usage_pct": 35.0 if override_status == "HEALTHY" else profile["cpu_usage_pct"],
        "memory_usage_pct": profile["memory_usage_pct"],
        "details": "Service stabilized after remediation" if override_status == "HEALTHY" else profile["details"],
        "dependencies": profile.get("dependencies", {}),
        "is_simulated": True
    }
    return result
