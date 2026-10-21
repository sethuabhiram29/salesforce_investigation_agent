"""PostgreSQL historical incidents & SOP repository with pgvector.

Responsibilities:
- Generate text embeddings using Ollama (nomic-embed-text)
- Store and retrieve historical incident records via cosine similarity (pgvector <=>)
- Query standard operating procedures (SOPs)
- Support domain filtering (Login, Object, Record, Application)
- Maintain fallback behavior when database or Ollama is unreachable in offline tests
"""

import logging
import os
from typing import Any, Dict, List, Optional

import psycopg
import requests
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

logger = logging.getLogger(__name__)
load_dotenv()


class PostgresIncidentRepository:
    """Repository for querying historical incidents and SOPs using pgvector."""

    def __init__(
        self,
        dsn: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        embed_model: Optional[str] = None,
        timeout: int = 15,
    ):
        self.dsn = dsn or os.getenv("PG_DSN")
        if not self.dsn:
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "5432")
            db = os.getenv("POSTGRES_DB", "sf_investigation")
            user = os.getenv("POSTGRES_USER", "postgres")
            password = os.getenv("POSTGRES_PASSWORD", "postgres")
            self.dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"

        self.ollama_base_url = (
            ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")
        self.embed_model = embed_model or os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        self.timeout = timeout

    def _get_connection(self):
        """Connect to PostgreSQL and register the pgvector data type."""
        conn = psycopg.connect(self.dsn, connect_timeout=self.timeout)
        try:
            register_vector(conn)
        except Exception as exc:
            logger.warning("Failed to register pgvector on connection: %s", exc)
        return conn

    def generate_embedding(self, text: str) -> List[float]:
        """Convert text into an embedding vector using Ollama."""
        url = f"{self.ollama_base_url}/api/embed"
        payload = {
            "model": self.embed_model,
            "input": text,
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings", [])
            if not embeddings:
                raise RuntimeError("Ollama returned empty embeddings array.")
            return embeddings[0]
        except Exception as exc:
            logger.error("Ollama embedding error for model '%s': %s", self.embed_model, exc)
            raise RuntimeError(
                f"Could not generate embedding via Ollama ({self.embed_model}): {exc}"
            ) from exc

    def search_historical_incidents(
        self,
        summary: str,
        description: str,
        domain: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve the top_k historical incidents most similar to the given incident.

        Parameters
        ----------
        summary:
            Summary of the incident (e.g., from ServiceNow short_description).
        description:
            Full description of the incident.
        domain:
            Optional domain filter ('Login', 'Object', 'Record', 'Application').
        top_k:
            Number of results to retrieve.
        """
        if not summary or not summary.strip():
            summary = "Salesforce incident"
        if not description or not description.strip():
            description = summary

        query_text = f"Summary: {summary.strip()}\nDescription: {description.strip()}"

        try:
            query_embedding = self.generate_embedding(query_text)
        except Exception as exc:
            logger.warning("Embedding generation failed, falling back to empty/mock results: %s", exc)
            return []

        sql = """
            SELECT
                h.incident_id,
                h.summary,
                h.description,
                h.domain,
                h.root_cause,
                h.resolution,
                1 - (
                    e.embedding <=> %s::vector
                ) AS similarity
            FROM public.historical_incident_embeddings AS e
            INNER JOIN public.historical_incidents AS h
                ON h.incident_id = e.incident_id
            WHERE (
                %s::text IS NULL
                OR LOWER(h.domain) = LOWER(%s::text)
            )
            ORDER BY
                e.embedding <=> %s::vector
            LIMIT %s;
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        sql,
                        (
                            query_embedding,
                            domain,
                            domain,
                            query_embedding,
                            top_k,
                        ),
                    )
                    rows = cur.fetchall()

            results = []
            for row in rows:
                results.append({
                    "incident_id": row[0],
                    "summary": row[1],
                    "description": row[2],
                    "domain": row[3],
                    "root_cause": row[4],
                    "resolution": row[5],
                    "similarity": float(row[6]),
                })
            return results
        except Exception as exc:
            logger.warning("PostgreSQL retrieval failed: %s", exc)
            return []

    def _search_fallback_catalog(
        self,
        summary: str,
        description: str,
        domain: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Fallback keyword and domain matcher using local canonical historical catalog."""
        try:
            from app.knowledge.sop_repository import sop_repository
            catalog = sop_repository.get_historical_incidents()
        except Exception:
            catalog = []
        if not catalog:
            try:
                from tests.fixtures.historical_incidents import FIXTURE_HISTORICAL_INCIDENTS
                catalog = list(FIXTURE_HISTORICAL_INCIDENTS)
            except Exception:
                return []

        text = f"{summary} {description}".lower()
        scored = []
        for item in catalog:
            item_domain = str(item.get("domain", "")).upper()
            if domain and item_domain != domain.upper():
                continue

            score = 0.60
            item_text = f"{item.get('summary', '')} {item.get('description', '')} {item.get('root_cause', '')}".lower()
            tokens = [w.strip(".,;:?!") for w in text.split() if len(w) > 3]
            matches = sum(1 for tok in tokens if tok in item_text)
            score += min(matches * 0.08, 0.35)
            scored.append({
                **item,
                "similarity": round(min(score, 0.95), 2),
            })

        scored.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        return scored[:top_k]

    def search_sops(
        self,
        query: str,
        domain: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Retrieve matching Standard Operating Procedures (SOPs) from pgvector."""
        if not query or not query.strip():
            return []

        try:
            query_embedding = self.generate_embedding(query.strip())
        except Exception as exc:
            logger.warning("Embedding generation failed for SOP search: %s", exc)
            return []

        sql = """
            SELECT
                id,
                domain,
                description,
                prerequisites,
                resolution_steps,
                1 - (embedding <=> %s::vector) AS similarity
            FROM public.sop_scenarios
            WHERE (
                %s::text IS NULL
                OR LOWER(domain) = LOWER(%s::text)
            )
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        sql,
                        (
                            query_embedding,
                            domain,
                            domain,
                            query_embedding,
                            top_k,
                        ),
                    )
                    rows = cur.fetchall()

            results = []
            for row in rows:
                results.append({
                    "id": row[0],
                    "domain": row[1],
                    "description": row[2],
                    "prerequisites": row[3],
                    "resolution_steps": row[4],
                    "similarity": float(row[5]),
                })
            return results
        except Exception as exc:
            logger.warning("PostgreSQL SOP retrieval failed: %s", exc)
            return []
