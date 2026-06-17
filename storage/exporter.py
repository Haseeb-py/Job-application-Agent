"""JSON exporter for generated bulk job application records."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def save_to_json(applications: list[dict[str, Any]], filepath: str) -> None:
    """Save application records to a JSON file."""

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(applications, file, indent=2, ensure_ascii=False)
    logger.info("Saved %d application records to %s", len(applications), path)
