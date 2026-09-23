import json
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.db.connection import get_db_connection

logger = logging.getLogger(__name__)

# In-memory stores for testing or fallback when database is offline
_in_memory_incidents: Dict[str, Dict[str, Any]] = {}
_in_memory_events: List[Dict[str, Any]] = []
_in_memory_docs: List[Dict[str, Any]] = []


class IncidentRepository:
    """Repository for CRUD operations on incidents table."""

    @staticmethod
    def create(
        title: str,
        description: str,
        service: str,
        source: str = "manual",
        external_id: Optional[str] = None,
        severity: Optional[str] = None,
        status: str = "OPEN",
        incident_id: Optional[str] = None
    ) -> Dict[str, Any]:
        target_id = incident_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        with get_db_connection() as conn:
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO incidents (
                                id, external_id, title, description, service,
                                severity, status, created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING *;
                            """,
                            (target_id, external_id, title, description, service, severity, status, now, now)
                        )
                        row = cur.fetchone()
                        if row:
                            return dict(row)
                except Exception as e:
                    logger.error(f"Error creating incident in database: {e}")

        # In-memory fallback
        record = {
            "id": target_id,
            "external_id": external_id,
            "title": title,
            "description": description,
            "service": service,
            "severity": severity,
            "status": status,
            "root_cause_hypothesis": None,
            "confidence": None,
            "recommended_action": None,
            "created_at": now,
            "updated_at": now,
            "resolved_at": None,
        }
        _in_memory_incidents[target_id] = record
        return record

    @staticmethod
    def get(incident_id: str) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM incidents WHERE id = %s;", (incident_id,))
                        row = cur.fetchone()
                        if row:
                            return dict(row)
                except Exception as e:
                    logger.error(f"Error fetching incident {incident_id} from database: {e}")

        return _in_memory_incidents.get(incident_id)

    @staticmethod
    def update(incident_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        updates["updated_at"] = now

        with get_db_connection() as conn:
            if conn is not None:
                try:
                    set_clauses = [f"{col} = %s" for col in updates.keys()]
                    query = f"UPDATE incidents SET {', '.join(set_clauses)} WHERE id = %s RETURNING *;"
                    values = list(updates.values()) + [incident_id]
                    with conn.cursor() as cur:
                        cur.execute(query, values)
                        row = cur.fetchone()
                        if row:
                            return dict(row)
                except Exception as e:
                    logger.error(f"Error updating incident {incident_id} in database: {e}")

        record = _in_memory_incidents.get(incident_id)
        if record:
            record.update(updates)
            return record
        return None

    @staticmethod
    def list_all(limit: int = 50) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM incidents ORDER BY created_at DESC LIMIT %s;", (limit,))
                        rows = cur.fetchall()
                        return [dict(r) for r in rows]
                except Exception as e:
                    logger.error(f"Error listing incidents from database: {e}")

        items = list(_in_memory_incidents.values())
        items.sort(key=lambda x: x["created_at"], reverse=True)
        return items[:limit]


class IncidentEventRepository:
    """Repository for audit trail incident_events table."""

    @staticmethod
    def create(
        incident_id: str,
        event_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        event_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        meta = metadata or {}

        with get_db_connection() as conn:
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO incident_events (
                                id, incident_id, event_type, message, metadata, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING *;
                            """,
                            (event_id, incident_id, event_type, message, json.dumps(meta), now)
                        )
                        row = cur.fetchone()
                        if row:
                            return dict(row)
                except Exception as e:
                    logger.error(f"Error creating incident event in database: {e}")

        event = {
            "id": event_id,
            "incident_id": incident_id,
            "event_type": event_type,
            "message": message,
            "metadata": meta,
            "created_at": now
        }
        _in_memory_events.append(event)
        return event

    @staticmethod
    def get_by_incident(incident_id: str) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT * FROM incident_events WHERE incident_id = %s ORDER BY created_at ASC;",
                            (incident_id,)
                        )
                        rows = cur.fetchall()
                        return [dict(r) for r in rows]
                except Exception as e:
                    logger.error(f"Error fetching events for incident {incident_id}: {e}")

        return [e for e in _in_memory_events if e["incident_id"] == incident_id]


class IncidentDocRepository:
    """Repository for RAG knowledge base runbooks in incident_docs with pgvector."""

    @staticmethod
    def insert(content: str, metadata: Dict[str, Any], embedding: List[float]) -> str:
        doc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        with get_db_connection() as conn:
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        # Vector formatted as string '[0.1, 0.2, ...]'
                        cur.execute(
                            """
                            INSERT INTO incident_docs (
                                id, content, metadata, embedding, created_at
                            ) VALUES (%s, %s, %s, %s, %s)
                            RETURNING id;
                            """,
                            (doc_id, content, json.dumps(metadata), str(embedding), now)
                        )
                        res = cur.fetchone()
                        if res:
                            return str(res["id"])
                except Exception as e:
                    logger.error(f"Error inserting doc into incident_docs: {e}")

        _in_memory_docs.append({
            "id": doc_id,
            "content": content,
            "metadata": metadata,
            "embedding": embedding,
            "created_at": now
        })
        return doc_id

    @staticmethod
    def count() -> int:
        with get_db_connection() as conn:
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) as count FROM incident_docs;")
                        row = cur.fetchone()
                        if row:
                            return row["count"]
                except Exception as e:
                    logger.error(f"Error counting docs: {e}")
        return len(_in_memory_docs)

    @staticmethod
    def doc_exists_for_source(source: str) -> bool:
        with get_db_connection() as conn:
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT 1 FROM incident_docs WHERE metadata->>'source' = %s LIMIT 1;",
                            (source,)
                        )
                        return cur.fetchone() is not None
                except Exception as e:
                    logger.error(f"Error checking if doc exists for source {source}: {e}")
        return any(d.get("metadata", {}).get("source") == source for d in _in_memory_docs)

    @staticmethod
    def similarity_search(
        query_embedding: List[float],
        service: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Perform cosine similarity search on pgvector embeddings."""
        with get_db_connection() as conn:
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        # pgvector cosine distance operator is <=>
                        # Cosine similarity = 1 - cosine_distance
                        if service:
                            query = """
                                SELECT id, content, metadata,
                                       1 - (embedding <=> %s::vector) AS similarity
                                FROM incident_docs
                                WHERE metadata->>'service' = %s
                                ORDER BY embedding <=> %s::vector
                                LIMIT %s;
                            """
                            cur.execute(query, (str(query_embedding), service.lower(), str(query_embedding), top_k))
                        else:
                            query = """
                                SELECT id, content, metadata,
                                       1 - (embedding <=> %s::vector) AS similarity
                                FROM incident_docs
                                ORDER BY embedding <=> %s::vector
                                LIMIT %s;
                            """
                            cur.execute(query, (str(query_embedding), str(query_embedding), top_k))

                        rows = cur.fetchall()
                        return [dict(r) for r in rows]
                except Exception as e:
                    logger.error(f"Error in vector similarity search: {e}")

        # In-memory cosine similarity fallback
        results = []
        for doc in _in_memory_docs:
            if service and doc["metadata"].get("service", "").lower() != service.lower():
                continue
            doc_emb = doc["embedding"]
            # Cosine similarity: (A . B) / (||A|| * ||B||)
            dot = sum(a * b for a, b in zip(query_embedding, doc_emb))
            norm_a = math.sqrt(sum(a * a for a in query_embedding))
            norm_b = math.sqrt(sum(b * b for b in doc_emb))
            sim = dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0
            results.append({
                "id": doc["id"],
                "content": doc["content"],
                "metadata": doc["metadata"],
                "similarity": round(sim, 4)
            })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
