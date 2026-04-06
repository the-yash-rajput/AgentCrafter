from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from models import Agent, Edge, Node
from type_defs import ExecutionContext, StatePayload


@dataclass(slots=True)
class GraphExecutionRequest:
    agent_id: int
    input_data: StatePayload = field(default_factory=dict)
    execution_context: ExecutionContext = field(default_factory=dict)

    def with_agent_call_stack(self, *, max_depth: int) -> "GraphExecutionRequest":
        prior_call_stack = list(self.execution_context.get("call_stack") or [])
        if self.agent_id in prior_call_stack:
            cycle = prior_call_stack + [self.agent_id]
            raise ValueError(f"Recursive agent call detected: {' -> '.join(map(str, cycle))}")
        if len(prior_call_stack) >= max_depth:
            raise ValueError(f"Nested agent call depth exceeded limit of {max_depth}")

        return GraphExecutionRequest(
            agent_id=self.agent_id,
            input_data=dict(self.input_data or {}),
            execution_context={
                **self.execution_context,
                "call_stack": [*prior_call_stack, self.agent_id],
            },
        )


@dataclass(slots=True)
class GraphFetchResult:
    agent: Agent
    nodes: list[Node]
    edges: list[Edge]


@dataclass(slots=True)
class LangGraphBuildRequest:
    graph_data: GraphFetchResult
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    execution_context: ExecutionContext = field(default_factory=dict)
    run_id: str | None = None


@dataclass(slots=True)
class CompiledGraphArtifact:
    graph: Any
    executable_node_names: set[str] = field(default_factory=set)


@dataclass(slots=True)
class TraceSession:
    trace: Any = None
    token: Any = None


@dataclass(slots=True)
class GraphRunResult:
    run_id: int
    status: str
    output: StatePayload = field(default_factory=dict)
    snapshots: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "output": self.output,
            "snapshots": self.snapshots,
        }


@dataclass(slots=True)
class GraphValidationReport:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
        }
