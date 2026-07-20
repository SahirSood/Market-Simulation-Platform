"""Smoke-check a deployed Market Simulation Platform API."""
from __future__ import annotations

import argparse
import json
from urllib import error, request

FRONTEND_PATHS = ["/", "/eval", "/retrieval", "/behavior", "/config"]


def _get_json(url: str, timeout: int) -> dict:
    with request.urlopen(url, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload)


def _get_status(url: str, timeout: int) -> int:
    with request.urlopen(url, timeout=timeout) as response:
        return response.status


def _post(url: str, api_key: str | None, timeout: int) -> int:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
        headers["X-Actor"] = "deploy-smoke"
    req = request.Request(url, data=b"{}", headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return response.status
    except error.HTTPError as exc:
        return exc.code


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check deployed API endpoints")
    parser.add_argument("--api-url", required=True, help="Base API URL, for example https://api.example.com")
    parser.add_argument("--frontend-url", help="Optional frontend URL to check for HTTP 200")
    parser.add_argument("--arena-api-key", help="Optional key for protected write-auth smoke check")
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    health = _get_json(f"{api_url}/health", args.timeout)
    if health.get("status") != "ok":
        print(f"ERROR: unexpected health payload: {health}")
        return 1
    print("API health check passed")

    docs_status = _get_status(f"{api_url}/docs", args.timeout)
    if docs_status != 200:
        print(f"ERROR: API docs returned HTTP {docs_status}")
        return 1
    print("API docs check passed")

    unauth_status = _post(f"{api_url}/ops/ingestion/run", None, args.timeout)
    if unauth_status not in {401, 422}:
        print(f"ERROR: protected write endpoint returned {unauth_status} without auth")
        return 1
    print("Protected write auth check passed")

    if args.arena_api_key:
        auth_status = _post(f"{api_url}/ops/ingestion/run", args.arena_api_key, args.timeout)
        if auth_status not in {200, 202, 400, 409, 422}:
            print(f"ERROR: authenticated write smoke returned unexpected status {auth_status}")
            return 1
        print("Authenticated write route is reachable")

    if args.frontend_url:
        frontend_url = args.frontend_url.rstrip("/")
        for path in FRONTEND_PATHS:
            status = _get_status(f"{frontend_url}{path}", args.timeout)
            if status != 200:
                print(f"ERROR: frontend route {path} returned HTTP {status}")
                return 1
        print("Frontend route checks passed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
