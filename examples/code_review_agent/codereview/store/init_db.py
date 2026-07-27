#
# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#

"""Idempotent database initialization."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from .review_store import DEFAULT_DB_URL, SqlReviewStore


def init_db(db_url: str = DEFAULT_DB_URL) -> None:
    """Create the five review tables and close the initialization engine."""

    store = SqlReviewStore(db_url)
    try:
        store.initialize()
    finally:
        store.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Initialize a configured review database."""

    parser = argparse.ArgumentParser(
        description="Initialize the automatic code-review database.",
    )
    parser.add_argument("--db-url", default=DEFAULT_DB_URL)
    args = parser.parse_args(argv)
    init_db(args.db_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
