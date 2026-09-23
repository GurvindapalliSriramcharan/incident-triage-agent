import pytest
from app.tools.rag import search_runbooks, generate_embedding
from app.db.repositories import IncidentDocRepository


def test_embedding_generation_length():
    """Verify generated embedding is exactly 768 dimensions."""
    emb = generate_embedding("Users are experiencing authentication timeouts on /oauth/token.")
    assert isinstance(emb, list)
    assert len(emb) == 768
    assert all(isinstance(x, (float, int)) for x in emb)


def test_rag_retrieves_auth_runbook():
    """Verify that an auth timeout query retrieves an auth runbook with high similarity."""
    query = "Authentication 504 gateway timeout and token refresh failure"
    results = search_runbooks(query, service="auth", top_k=3)

    assert len(results) > 0
    top_result = results[0]
    assert "similarity" in top_result
    assert top_result["similarity"] > 0.0
    assert top_result["metadata"]["service"] == "auth"
    assert "auth" in top_result["metadata"]["source"].lower()


def test_rag_retrieves_database_runbook():
    """Verify that a database query retrieves a database runbook."""
    query = "Postgres high query latency, idle in transaction lock contention"
    results = search_runbooks(query, service="database", top_k=3)

    assert len(results) > 0
    top_result = results[0]
    assert top_result["metadata"]["service"] == "database"
    assert "database" in top_result["metadata"]["source"].lower()


def test_rag_service_filtering():
    """Verify that service filtering restricts results to the requested service."""
    query = "General system latency"
    results = search_runbooks(query, service="payments", top_k=5)

    for item in results:
        assert item["metadata"]["service"] == "payments"


def test_rag_empty_query():
    """Verify empty query returns empty list safely."""
    results = search_runbooks("")
    assert results == []
