import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.smoke_deployment import FRONTEND_PATHS


def test_deploy_smoke_covers_public_recruiter_routes() -> None:
    assert FRONTEND_PATHS == [
        "/",
        "/bots",
        "/book",
        "/behavior",
        "/eval",
        "/retrieval",
        "/config",
    ]
