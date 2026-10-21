"""Ingest Salesforce SOPs and historical incidents into PostgreSQL/pgvector.

SOP storage:
    public.sop_scenarios
    - SOP text fields and embedding in the same table.

Historical incident storage:
    public.historical_incidents
    - Exactly six required text columns: incident_id, summary, description, domain, root_cause, resolution.

    public.historical_incident_embeddings
    - incident_id
    - embedding

Embeddings are generated using Ollama (nomic-embed-text, 768 dimensions).
"""

import os
from pathlib import Path
from typing import List, Tuple, Dict, Any

import ollama
import pandas as pd
import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PG_DSN = os.getenv(
    "PG_DSN",
    f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:{os.getenv('POSTGRES_PASSWORD', 'postgres')}@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'sf_investigation')}"
)

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
)

EMBED_MODEL = os.getenv(
    "OLLAMA_EMBED_MODEL",
    "nomic-embed-text",
)

EMBEDDING_DIMENSIONS = int(
    os.getenv("EMBEDDING_DIMENSIONS", "768")
)

BATCH_SIZE = int(
    os.getenv("EMBED_BATCH_SIZE", "32")
)

SOP_SOURCE_FILE = ROOT / os.getenv(
    "SOP_SOURCE_FILE",
    "data/sop_scenarios_selected_sheets.xlsx",
)

HISTORICAL_FILE = ROOT / os.getenv(
    "HISTORICAL_FILE",
    "data/historical_incidents.xlsx",
)

HISTORICAL_COLUMNS = [
    "incident_id",
    "summary",
    "description",
    "domain",
    "root_cause",
    "resolution",
]

ALLOWED_DOMAINS = {
    "login": "Login",
    "object": "Object",
    "record": "Record",
    "application": "Application",
}


def get_ollama_client() -> ollama.Client:
    return ollama.Client(host=OLLAMA_BASE_URL)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    """Create a PostgreSQL connection and register pgvector."""
    conn = psycopg.connect(PG_DSN)
    register_vector(conn)
    return conn


def text_cell(value: Any) -> str:
    """Convert an Excel cell into trimmed text."""
    if pd.isna(value):
        return ""
    return str(value).strip()


# ============================================================
# EMBEDDING GENERATION
# ============================================================

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Generate embeddings through Ollama in batches."""
    if not texts:
        return []

    client = get_ollama_client()
    all_vectors = []

    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]

        response = client.embed(
            model=EMBED_MODEL,
            input=batch,
        )

        vectors = response["embeddings"]

        if len(vectors) != len(batch):
            raise RuntimeError("Ollama returned an unexpected number of embeddings.")

        for vector in vectors:
            if len(vector) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}, received {len(vector)}."
                )

        all_vectors.extend(vectors)

    return all_vectors


# ============================================================
# SOP INGESTION
# ============================================================

def load_selected_sop_rows() -> Tuple[List[Dict[str, Any]], List[str]]:
    """Load and validate records from the prepared SOP workbook."""
    if not SOP_SOURCE_FILE.exists():
        raise FileNotFoundError(f"SOP workbook not found: {SOP_SOURCE_FILE}")

    df = pd.read_excel(
        SOP_SOURCE_FILE,
        sheet_name="sop_scenarios",
    )

    required = [
        "id",
        "domain",
        "description",
        "prerequisites",
        "resolution_steps",
    ]

    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(f"SOP workbook is missing columns: {sorted(missing)}")

    df = df[required].copy()
    output = []
    skipped = []

    for row_index, row in df.iterrows():
        sop_id = text_cell(row["id"])
        raw_domain = text_cell(row["domain"]).lower()
        description = text_cell(row["description"])
        prerequisites = text_cell(row["prerequisites"])
        resolution_steps = text_cell(row["resolution_steps"])

        domain = ALLOWED_DOMAINS.get(raw_domain)

        if not sop_id or not domain or not description:
            skipped.append(
                f"Excel row {row_index + 2}: missing ID, valid domain, or description"
            )
            continue

        if not resolution_steps:
            skipped.append(f"{sop_id}: resolution_steps is blank")
            continue

        output.append({
            "id": sop_id,
            "domain": domain,
            "description": description,
            "prerequisites": prerequisites,
            "resolution_steps": resolution_steps,
            "source_sheet": "sop_scenarios",
        })

    ids = [record["id"] for record in output]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate SOP IDs found in the workbook.")

    print(f"Valid SOP records found: {len(output)}")
    print(f"SOP records skipped: {len(skipped)}")

    return output, skipped


def ingest_sops() -> None:
    """Store SOP text and its embedding in the public.sop_scenarios table."""
    records, skipped = load_selected_sop_rows()

    if not records:
        print("No complete SOP records found to ingest.")
        for message in skipped:
            print("SKIPPED:", message)
        return

    texts = [
        f"Domain: {record['domain']}\n"
        f"Description: {record['description']}\n"
        f"Prerequisites: {record['prerequisites']}\n"
        f"Resolution steps: {record['resolution_steps']}"
        for record in records
    ]

    vectors = embed_texts(texts)

    sql = """
        INSERT INTO public.sop_scenarios (
            id,
            domain,
            description,
            prerequisites,
            resolution_steps,
            embedding,
            source_sheet
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            domain = EXCLUDED.domain,
            description = EXCLUDED.description,
            prerequisites = EXCLUDED.prerequisites,
            resolution_steps = EXCLUDED.resolution_steps,
            embedding = EXCLUDED.embedding,
            source_sheet = EXCLUDED.source_sheet,
            updated_at = NOW()
    """

    values = [
        (
            record["id"],
            record["domain"],
            record["description"],
            record["prerequisites"],
            record["resolution_steps"],
            vector,
            record["source_sheet"],
        )
        for record, vector in zip(records, vectors)
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, values)

    print(f"Ingested/updated {len(values)} SOP records.")
    for message in skipped:
        print("SKIPPED:", message)


# ============================================================
# HISTORICAL INCIDENT INGESTION
# ============================================================

def load_historical_incidents() -> pd.DataFrame:
    """Load and validate six business-data columns from Excel."""
    if not HISTORICAL_FILE.exists():
        raise FileNotFoundError(f"Historical incident file not found: {HISTORICAL_FILE}")

    df = pd.read_excel(HISTORICAL_FILE)
    df.columns = [str(col).strip().lower() for col in df.columns]

    if len(df.columns) != len(set(df.columns)):
        raise ValueError("Duplicate column names found after header normalization.")

    missing = set(HISTORICAL_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Historical incident workbook missing columns: {sorted(missing)}")

    df = df[HISTORICAL_COLUMNS].copy()
    for col in HISTORICAL_COLUMNS:
        df[col] = df[col].map(text_cell)

    df = df[df.apply(lambda row: any(val != "" for val in row), axis=1)].copy()

    if df.empty:
        print("The historical incident workbook contains no records.")
        return df

    for col in HISTORICAL_COLUMNS:
        blank_mask = df[col].eq("")
        if blank_mask.any():
            bad_ids = df.loc[blank_mask, "incident_id"].tolist()
            raise ValueError(f"Blank required field '{col}' in incident IDs: {bad_ids}")

    if df["incident_id"].duplicated().any():
        duplicates = df.loc[df["incident_id"].duplicated(keep=False), "incident_id"].tolist()
        raise ValueError(f"Duplicate historical incident IDs: {duplicates}")

    normalized_domains = df["domain"].str.lower()
    invalid_domains = sorted(set(normalized_domains) - set(ALLOWED_DOMAINS))
    if invalid_domains:
        raise ValueError(f"Unsupported domains: {invalid_domains}. Use Login, Object, Record, or Application.")

    df["domain"] = normalized_domains.map(ALLOWED_DOMAINS)
    return df


def ingest_historical_incidents() -> None:
    """Upsert historical incidents and their embeddings in a single transaction."""
    df = load_historical_incidents()
    if df.empty:
        print("No historical incidents found.")
        return

    texts = [
        f"Domain: {row.domain}\n"
        f"Root cause: {row.root_cause}\n"
        f"Summary: {row.summary}\n"
        f"Description: {row.description}\n"
        f"Resolution: {row.resolution}"
        for row in df.itertuples(index=False)
    ]

    vectors = embed_texts(texts)

    incident_sql = """
        INSERT INTO public.historical_incidents (
            incident_id,
            summary,
            description,
            domain,
            root_cause,
            resolution
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (incident_id) DO UPDATE SET
            summary = EXCLUDED.summary,
            description = EXCLUDED.description,
            domain = EXCLUDED.domain,
            root_cause = EXCLUDED.root_cause,
            resolution = EXCLUDED.resolution
    """

    incident_values = [
        (
            row.incident_id,
            row.summary,
            row.description,
            row.domain,
            row.root_cause,
            row.resolution,
        )
        for row in df.itertuples(index=False)
    ]

    embedding_sql = """
        INSERT INTO public.historical_incident_embeddings (
            incident_id,
            embedding
        )
        VALUES (%s, %s)
        ON CONFLICT (incident_id) DO UPDATE SET
            embedding = EXCLUDED.embedding
    """

    embedding_values = [
        (row.incident_id, vector)
        for row, vector in zip(df.itertuples(index=False), vectors)
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(incident_sql, incident_values)
            cur.executemany(embedding_sql, embedding_values)

    print(f"Ingested/updated {len(incident_values)} historical incidents and embeddings.")


def init_database_schema():
    """Apply db_schema.sql automatically using Python so psql is not required."""
    schema_path = ROOT / "scripts" / "db_schema.sql"
    if not schema_path.exists():
        print(f"Warning: {schema_path} not found. Skipping schema setup.")
        return

    print("Checking and applying database schema from scripts/db_schema.sql...")
    sql = schema_path.read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    print("Database schema successfully verified/created.")


def main():
    # 1. Apply schema automatically
    init_database_schema()

    # 2. Ingest SOPs and historical incidents
    if SOP_SOURCE_FILE.exists():
        ingest_sops()
    else:
        print(f"SOP source file {SOP_SOURCE_FILE} not found. Skipping SOP ingestion.")

    if HISTORICAL_FILE.exists():
        ingest_historical_incidents()
    else:
        print(f"Historical incident file {HISTORICAL_FILE} not found. Skipping historical ingestion.")


if __name__ == "__main__":
    main()
