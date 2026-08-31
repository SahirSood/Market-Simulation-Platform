import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.smoke_deployment import FRONTEND_PATHS


def test_deploy_smoke_covers_public_recruiter_routes() -> None:
    assert FRONTEND_PATHS == [
        "/",
        "/brief",
        "/research",
        "/research?tab=evaluation",
        "/research?tab=evidence",
        "/research?tab=bots",
        "/research?tab=book",
        "/research?tab=behavior",
        "/research?tab=config",
    ]
