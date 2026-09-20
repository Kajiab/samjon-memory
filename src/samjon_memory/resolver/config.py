"""Typed configuration for Samjon Memory Resolver V1."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResolverConfig:
    database_path: str = field(
        default_factory=lambda: os.environ.get(
            "SAMJON_RESOLVER_DATABASE_PATH", "./data/samjon_resolver.sqlite"
        )
    )
    fts5_required: bool = field(
        default_factory=lambda: os.environ.get(
            "SAMJON_RESOLVER_FTS5_REQUIRED", "true"
        ).lower()
        in ("true", "1", "yes", "on")
    )


def load_config() -> ResolverConfig:
    """Build Resolver config from the environment."""
    return ResolverConfig(
        database_path=os.environ.get(
            "SAMJON_RESOLVER_DATABASE_PATH", "./data/samjon_resolver.sqlite"
        ),
        fts5_required=os.environ.get(
            "SAMJON_RESOLVER_FTS5_REQUIRED", "true"
        ).lower()
        in ("true", "1", "yes", "on"),
    )


config = load_config()
