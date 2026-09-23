import pytest
from app.tools.health import check_service_health


def test_health_known_service_auth():
    """Verify health telemetry for known degraded auth service."""
    result = check_service_health("auth")
    assert result["service"] == "auth"
    assert result["status"] == "DEGRADED"
    assert result["latency_ms"] > 500
    assert result["error_rate_pct"] > 10.0
    assert result["is_simulated"] is True
    assert "redis_cache" in result["dependencies"]


def test_health_known_service_database():
    """Verify health telemetry for known healthy database service."""
    result = check_service_health("database")
    assert result["service"] == "database"
    assert result["status"] == "HEALTHY"
    assert result["latency_ms"] < 50
    assert result["error_rate_pct"] < 1.0
    assert result["is_simulated"] is True


def test_health_known_service_payments():
    """Verify health telemetry for known payments service."""
    result = check_service_health("payments")
    assert result["service"] == "payments"
    assert result["status"] == "HEALTHY"
    assert result["is_simulated"] is True


def test_health_unknown_service():
    """Verify graceful handling and UNKNOWN status for an unrecognized service."""
    result = check_service_health("non_existent_microservice_xyz")
    assert result["status"] == "UNKNOWN"
    assert result["latency_ms"] == -1
    assert result["error_rate_pct"] == -1.0
    assert "not recognized" in result["details"]
    assert result["is_simulated"] is True


def test_health_override_post_remediation():
    """Verify health check returns stabilized status when override is applied."""
    result = check_service_health("auth", override_status="HEALTHY")
    assert result["service"] == "auth"
    assert result["status"] == "HEALTHY"
    assert result["error_rate_pct"] == 0.0
    assert "stabilized" in result["details"].lower()
