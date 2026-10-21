"""Salesforce Connection & MCP Verification Script.

Tests and displays the active connection state with your Salesforce org or Salesforce MCP server.
Run with:
    python scripts/test_salesforce_connection.py
"""

import json
import os
import sys
from pathlib import Path

# Ensure root directory is in sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from app.integrations.salesforce.client import salesforce_client


def print_banner(text: str):
    print("\n" + "=" * 65)
    print(f"  {text}")
    print("=" * 65)


def test_connection():
    print_banner("SALESFORCE CONNECTION & MCP DIAGNOSTIC")

    # 1. Inspect Environment Variables
    mcp_url = os.environ.get("SALESFORCE_MCP_URL")
    instance_url = os.environ.get("SALESFORCE_INSTANCE_URL") or os.environ.get("SALESFORCE_LOGIN_URL")
    username = os.environ.get("SALESFORCE_USERNAME")
    password = os.environ.get("SALESFORCE_PASSWORD")
    token = os.environ.get("SALESFORCE_SECURITY_TOKEN")
    access_token = os.environ.get("SALESFORCE_ACCESS_TOKEN")
    client_id = os.environ.get("SALESFORCE_CLIENT_ID")
    private_key = os.environ.get("SALESFORCE_PRIVATE_KEY") or os.environ.get("SALESFORCE_PRIVATE_KEY_PATH") or r"C:\salesforce\certs\server.key"

    print("[1] Configured Environment Variables in .env:")
    print(f"    - SALESFORCE_MCP_URL       : {mcp_url or '(not set)'}")
    print(f"    - SALESFORCE_INSTANCE_URL  : {instance_url or '(not set)'}")
    print(f"    - SALESFORCE_USERNAME      : {username or '(not set)'}")
    print(f"    - SALESFORCE_CLIENT_ID     : {client_id[:10] + '...' if client_id else '(not set)'}")
    print(f"    - SALESFORCE_PRIVATE_KEY   : {private_key} ({'FOUND' if os.path.exists(private_key) else 'NOT FOUND'})")
    print(f"    - SALESFORCE_PASSWORD      : {'*' * len(password) if password else '(not set)'}")
    print(f"    - SALESFORCE_SECURITY_TOKEN: {'*' * len(token) if token else '(not set)'}")
    print(f"    - SALESFORCE_ACCESS_TOKEN  : {'(present)' if access_token and access_token != 'fixture' else '(not set / fixture)'}")

    # 2. Check MCP Server Connection
    print("\n[2] Testing Salesforce MCP Server...")
    if mcp_url:
        mcp_res = salesforce_client.call_mcp_tool("ping", {})
        if mcp_res is not None:
            print(f"    SUCCESS: Connected to MCP server at {mcp_url}")
        else:
            print(f"    INFO: MCP server at {mcp_url} did not respond to 'ping'. Probing tools directly...")
    else:
        print("    INFO: No SALESFORCE_MCP_URL configured. Skipping MCP HTTP endpoint.")

    # 3. Check Direct Salesforce Authentication
    print("\n[3] Testing Direct Salesforce Org Authentication...")
    authenticated = salesforce_client.authenticate_direct()
    if authenticated and salesforce_client.access_token and salesforce_client.access_token != "fixture":
        print(f"    SUCCESS: Authenticated with live Salesforce org!")
        print(f"    Instance URL : {salesforce_client.instance_url}")
        print(f"    Access Token : {salesforce_client.access_token[:15]}... [REDACTED]")
    else:
        print("    STATUS: Not connected to live Salesforce. Currently using offline Fixtures.")
        if not (username and password) and not (access_token and access_token != "fixture"):
            print("\n    To link your real Salesforce org, add these to your .env file:")
            print("    ---------------------------------------------------------")
            print("    SALESFORCE_INSTANCE_URL=https://login.salesforce.com")
            print("    SALESFORCE_USERNAME=your.salesforce.username@company.com")
            print("    SALESFORCE_PASSWORD=YourPassword123")
            print("    SALESFORCE_SECURITY_TOKEN=OptionalSecurityToken")
            print("    ---------------------------------------------------------")
            print("    (Or if using an MCP server: SALESFORCE_MCP_URL=http://localhost:8000/mcp)")
            return

    # 4. Run Test SOQL Query
    print("\n[4] Executing Test SOQL Query (User probe)...")
    try:
        users = salesforce_client.execute_soql(
            "SELECT Id, Username, Email, FirstName, LastName, IsActive FROM User LIMIT 3"
        )
        print(f"    Retrieved {len(users)} user record(s):")
        for u in users:
            print(f"      - {u.get('Username')} (Email: {u.get('Email')}, Active: {u.get('IsActive')})")
    except Exception as e:
        print(f"    SOQL Query error: {e}")

    # 5. Run Test SOSL Search
    print("\n[5] Executing Test SOSL Search (Global Find probe)...")
    try:
        sosl_res = salesforce_client.execute_sosl(
            "FIND {test} IN ALL FIELDS RETURNING User(Id, Username)"
        )
        print(f"    SOSL Search returned {len(sosl_res)} match(es).")
    except Exception as e:
        print(f"    SOSL Search error: {e}")

    print_banner("DIAGNOSTIC COMPLETE")


if __name__ == "__main__":
    test_connection()
