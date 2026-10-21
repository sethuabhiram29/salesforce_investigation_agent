-- ============================================================
-- Salesforce Support Agent - Knowledge Base Schema (pgvector)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Standard Operating Procedures (SOPs)
CREATE TABLE IF NOT EXISTS public.sop_scenarios (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL CHECK (domain IN ('Login', 'Record', 'Object', 'Application')),
    description TEXT NOT NULL,
    prerequisites TEXT NOT NULL DEFAULT '',
    resolution_steps TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    source_sheet TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Historical Incidents (Business Data)
CREATE TABLE IF NOT EXISTS public.historical_incidents (
    incident_id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    description TEXT NOT NULL,
    domain TEXT NOT NULL CHECK (domain IN ('Login', 'Record', 'Object', 'Application')),
    root_cause TEXT NOT NULL,
    resolution TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Historical Incident Embeddings
CREATE TABLE IF NOT EXISTS public.historical_incident_embeddings (
    incident_id TEXT PRIMARY KEY REFERENCES public.historical_incidents(incident_id) ON DELETE CASCADE,
    embedding VECTOR(768) NOT NULL
);

-- Cosine Distance Indexes for Fast Semantic Search
CREATE INDEX IF NOT EXISTS idx_sop_scenarios_embedding
ON public.sop_scenarios USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_sop_scenarios_domain
ON public.sop_scenarios (domain);

CREATE INDEX IF NOT EXISTS idx_historical_incident_embeddings_vector
ON public.historical_incident_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_historical_incidents_domain
ON public.historical_incidents (domain);
