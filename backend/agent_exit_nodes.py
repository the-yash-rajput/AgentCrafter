from __future__ import annotations

from typing import Any


def normalize_exit_nodes(exit_nodes: Any = None, exit_node: Any = None) -> list[str]:
    values: list[Any] = []

    if isinstance(exit_nodes, str):
        values.append(exit_nodes)
    elif isinstance(exit_nodes, (list, tuple, set)):
        values.extend(exit_nodes)

    if isinstance(exit_node, str):
        values.append(exit_node)

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


def sync_exit_fields(data: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_exit_nodes(data.get("exit_nodes"), data.get("exit_node"))
    data["exit_nodes"] = normalized
    data["exit_node"] = normalized[0] if normalized else None
    return data


def get_agent_exit_nodes(agent: Any) -> list[str]:
    return normalize_exit_nodes(
        getattr(agent, "exit_nodes", None),
        getattr(agent, "exit_node", None),
    )
