from __future__ import annotations

from typing import Any


def normalize_exit_nodes(exit_nodes: Any = None) -> list[str]:
    values: list[Any] = []

    if isinstance(exit_nodes, str):
        values.append(exit_nodes)
    elif isinstance(exit_nodes, (list, tuple, set)):
        values.extend(exit_nodes)

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        name = value.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)

    return normalized


def get_agent_exit_nodes(agent: Any) -> list[str]:
    return normalize_exit_nodes(getattr(agent, "exit_nodes", None))
