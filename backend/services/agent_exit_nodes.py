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


def sync_exit_fields(data: dict[str, Any]) -> dict[str, Any]:
    raw_exit_nodes = data.get("exit_nodes")
    legacy_exit_node = data.get("exit_node")
    if raw_exit_nodes is None and isinstance(legacy_exit_node, str):
        raw_exit_nodes = [legacy_exit_node]

    normalized = normalize_exit_nodes(raw_exit_nodes)
    data["exit_nodes"] = normalized
    data.pop("exit_node", None)
    return data


def get_agent_exit_nodes(agent: Any) -> list[str]:
    return normalize_exit_nodes(getattr(agent, "exit_nodes", None))
