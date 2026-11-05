"""ngrok Tunnel Host for Salesforce Investigation Agent Streamlit UI.

Allows exposing either local Streamlit instance (default port 8501 or 8502)
to an external ngrok domain for testing by remote users.

Usage:
    python host.py              # forwards localhost:8501
    python host.py 8502         # forwards localhost:8502
    python host.py --port 8502  # forwards localhost:8502
"""

import os
import sys
import time
import argparse
from pathlib import Path

# Load environment variables from .env if available
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

import ngrok


def parse_args():
    parser = argparse.ArgumentParser(description="Forward Streamlit UI via ngrok tunnel")
    parser.add_argument(
        "port_pos",
        nargs="?",
        type=int,
        default=None,
        help="Target port (positional, e.g. 8501 or 8502)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8501,
        help="Target local port (default: 8501)",
    )
    parser.add_argument(
        "--domain",
        "-d",
        type=str,
        default="clad-silent-quiet.ngrok-free.dev",
        help="Static ngrok domain or subdomain",
    )
    parser.add_argument(
        "--authtoken",
        "-t",
        type=str,
        default=None,
        help="ngrok authtoken (overrides NGROK_AUTHTOKEN env var)",
    )
    return parser.parse_args()


def connect_ngrok():
    args = parse_args()
    target_port = args.port_pos if args.port_pos is not None else args.port
    authtoken = args.authtoken or os.environ.get("NGROK_AUTHTOKEN")

    forward_kwargs = {
        "addr": f"localhost:{target_port}",
        "domain": args.domain,
    }

    if authtoken:
        forward_kwargs["authtoken"] = authtoken
    else:
        forward_kwargs["authtoken_from_env"] = True

    print("=" * 60)
    print(f"  Starting ngrok tunnel for Streamlit on port {target_port}...")
    print(f"  Target Domain: {args.domain}")
    print("=" * 60)

    try:
        listener = ngrok.forward(**forward_kwargs)
        public_url = listener.url()
        print(f"\n[OK] ngrok tunnel is LIVE!")
        print(f"  Public URL:   {public_url}")
        print(f"  Forwarding to: http://localhost:{target_port}")
        print("\nPress Ctrl+C to stop the tunnel.\n")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping ngrok tunnel...")
    except Exception as e:
        err_msg = str(e)
        print(f"\n[ERROR] Failed to start ngrok tunnel: {err_msg}")
        if "ERR_NGROK_4018" in err_msg or "not authenticated" in err_msg.lower():
            print("\nHint: ngrok requires an authtoken.")
            print("You can set it via:")
            print("  set NGROK_AUTHTOKEN=your_token_here")
            print("  or: python host.py --authtoken your_token_here")
            print("  or add NGROK_AUTHTOKEN=... in your .env file.\n")
        sys.exit(1)


if __name__ == "__main__":
    connect_ngrok()
