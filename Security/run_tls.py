"""
Deployment-ready TLS runner for FastAPI.

Usage (PowerShell):
  $env:TLS_CERT_FILE="C:\path\to\cert.pem"
  $env:TLS_KEY_FILE="C:\path\to\key.pem"
  $env:TLS_CA_FILE="C:\path\to\ca.pem"   # optional
  $env:TLS_HOST="0.0.0.0"
  $env:TLS_PORT="443"
  "C:\Program Files\Python311\python.exe" Security\run_tls.py
"""

from __future__ import annotations

import os
import sys
import uvicorn

from Security.https_tls import create_ssl_context


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value if value not in (None, "") else None


def main() -> None:
    certfile = _get_env("TLS_CERT_FILE")
    keyfile = _get_env("TLS_KEY_FILE")
    cafile = _get_env("TLS_CA_FILE")
    host = _get_env("TLS_HOST", "0.0.0.0")
    port = int(_get_env("TLS_PORT", "443"))

    if not certfile or not keyfile:
        print("TLS_CERT_FILE and TLS_KEY_FILE are required.", file=sys.stderr)
        sys.exit(1)

    ssl_context = create_ssl_context(certfile=certfile, keyfile=keyfile, cafile=cafile)

    config = uvicorn.Config(
        "main:app",
        host=host,
        port=port,
        ssl=ssl_context,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
