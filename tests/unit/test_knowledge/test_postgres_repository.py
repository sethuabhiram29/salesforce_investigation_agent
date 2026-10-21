"""Tests for PostgreSQL historical incidents repository."""

import unittest
from unittest.mock import MagicMock, patch

from app.knowledge.postgres_repository import PostgresIncidentRepository
from app.tools.historical_incidents import (
    search_similar_incidents,
    search_sop_procedures,
    fetch_historical_context_for_state,
)


class TestPostgresRepository(unittest.TestCase):
    def test_repository_initialization(self):
        repo = PostgresIncidentRepository(
            dsn="postgresql://user:pass@localhost:5432/testdb",
            ollama_base_url="http://localhost:11434",
            embed_model="nomic-embed-text",
        )
        self.assertEqual(repo.dsn, "postgresql://user:pass@localhost:5432/testdb")
        self.assertEqual(repo.ollama_base_url, "http://localhost:11434")
        self.assertEqual(repo.embed_model, "nomic-embed-text")

    @patch("requests.post")
    def test_generate_embedding(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "embeddings": [[0.1, 0.2, 0.3]]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        repo = PostgresIncidentRepository()
        embedding = repo.generate_embedding("Cannot login to Salesforce")

        self.assertEqual(embedding, [0.1, 0.2, 0.3])
        mock_post.assert_called_once()

    @patch.object(PostgresIncidentRepository, "generate_embedding")
    @patch.object(PostgresIncidentRepository, "_get_connection")
    def test_search_historical_incidents(self, mock_conn, mock_embed):
        mock_embed.return_value = [0.1] * 768

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (
                "INC0091823",
                "SSO login failure",
                "User Jane Doe cannot sign in",
                "Login",
                "LOGIN-4: Federation ID missing",
                "Added FederationIdentifier",
                0.92,
            )
        ]
        mock_cursor_context = MagicMock()
        mock_cursor_context.__enter__.return_value = mock_cursor
        mock_cursor_context.__exit__.return_value = None

        mock_connection_instance = MagicMock()
        mock_connection_instance.cursor.return_value = mock_cursor_context
        mock_conn.return_value.__enter__.return_value = mock_connection_instance

        repo = PostgresIncidentRepository()
        results = repo.search_historical_incidents(
            summary="User cannot login",
            description="SAML SSO error reported",
            domain="Login",
            top_k=1,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["incident_id"], "INC0091823")
        self.assertEqual(results[0]["similarity"], 0.92)
        self.assertEqual(results[0]["root_cause"], "LOGIN-4: Federation ID missing")

    def test_fetch_historical_context_for_state_graceful_on_db_down(self):
        with patch.object(
            PostgresIncidentRepository,
            "generate_embedding",
            side_effect=RuntimeError("Ollama down"),
        ):
            results = fetch_historical_context_for_state(
                incident_summary="Cannot sign in",
                incident_description="Federation ID blank",
                domain="Login",
            )
            self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
