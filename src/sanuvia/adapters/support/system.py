"""System Clock and IdGenerator adapters for real (non-test) runs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


class SystemClock:
    """Wall-clock time (UTC, timezone-aware). Implements the ``Clock`` port."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class UuidGenerator:
    """UUID4-based ids with a readable ``kind`` prefix. Implements the
    ``IdGenerator`` port."""

    def new_id(self, kind: str) -> str:
        return f"{kind}-{uuid.uuid4()}"
