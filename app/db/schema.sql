-- Enable UUID and pgvector extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS vector;

-- Incidents table
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(100),
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    service VARCHAR(100) NOT NULL,
    severity VARCHAR(50),
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
    root_cause_hypothesis TEXT,
    confidence NUMERIC(4, 2),
    recommended_action VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ
);

-- Incident audit events table
CREATE TABLE IF NOT EXISTS incident_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- RAG knowledge base for incident runbooks
CREATE TABLE IF NOT EXISTS incident_docs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_service ON incidents(service);
CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_incident_events_incident_id ON incident_events(incident_id);
CREATE INDEX IF NOT EXISTS idx_incident_events_event_type ON incident_events(event_type);
CREATE INDEX IF NOT EXISTS idx_incident_events_created_at ON incident_events(created_at ASC);

CREATE INDEX IF NOT EXISTS idx_incident_docs_metadata ON incident_docs USING GIN(metadata);
-- Optional vector cosine index (works with HNSW on pgvector >= 0.5.0)
CREATE INDEX IF NOT EXISTS idx_incident_docs_embedding_hnsw 
    ON incident_docs USING hnsw (embedding vector_cosine_ops);
