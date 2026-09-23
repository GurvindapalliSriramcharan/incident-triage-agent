import datetime
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Predefined realistic log streams for simulation
LOG_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "auth": [
        {
            "level": "WARN",
            "logger": "auth.cache.redis",
            "message": "Redis cluster connection latency 480ms exceeded threshold (50ms). Pool utilization 98%."
        },
        {
            "level": "ERROR",
            "logger": "auth.tokens.jwt",
            "message": "Token refresh timeout for client_id=mobile-app-prod after 5000ms: Redis read lock wait timeout."
        },
        {
            "level": "ERROR",
            "logger": "auth.http.middleware",
            "message": "HTTP 504 Gateway Timeout on POST /oauth/v2/token - upstream auth replica not responding."
        },
        {
            "level": "WARN",
            "logger": "auth.cluster.health",
            "message": "Replica auth-worker-pod-71b experiencing high garbage collection pause (1420ms)."
        },
        {
            "level": "INFO",
            "logger": "auth.security.audit",
            "message": "Blacklist cache check experiencing read lock contention. 412 queued token verifications."
        }
    ],
    "database": [
        {
            "level": "WARN",
            "logger": "pg.stat_activity",
            "message": "Detected 3 idle-in-transaction connections open > 300 seconds on user_shard_01."
        },
        {
            "level": "INFO",
            "logger": "pg.replication",
            "message": "Streaming replication lag between primary and replica-01 is 14ms (nominal)."
        },
        {
            "level": "WARN",
            "logger": "pg.vacuum",
            "message": "Table 'sessions' dead tuple count exceeds 45,000; autovacuum queued."
        }
    ],
    "payments": [
        {
            "level": "WARN",
            "logger": "payment.gateway.stripe",
            "message": "Gateway response latency elevated: p99 at 920ms."
        },
        {
            "level": "INFO",
            "logger": "payment.webhook.handler",
            "message": "Processed 1,420 charge.succeeded events in last 60 seconds with 100% idempotency match."
        }
    ]
}


def get_service_logs(service: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieve recent simulated log entries for a service.
    Clearly simulated infrastructure tool for incident triage MVP.
    """
    service_normalized = (service or "").strip().lower()
    raw_logs = LOG_TEMPLATES.get(service_normalized, [
        {
            "level": "INFO",
            "logger": f"{service_normalized}.app",
            "message": f"Service telemetry stream started for {service_normalized}."
        }
    ])

    now = datetime.datetime.now(datetime.timezone.utc)
    results = []
    for i, log in enumerate(raw_logs[:limit]):
        # Give realistic staggered timestamps in the past 10 minutes
        timestamp = (now - datetime.timedelta(seconds=(len(raw_logs) - i) * 45)).isoformat()
        results.append({
            "timestamp": timestamp,
            "level": log["level"],
            "logger": log["logger"],
            "message": log["message"],
            "service": service_normalized,
            "is_simulated": True
        })
    return results
