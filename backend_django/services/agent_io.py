from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.agent import Agent
from models.agent_version import AgentVersion
from models.edge import Edge
from models.node import Node
from models.enums import AgentStatus, EdgeType
from services.exceptions import ValidationError
from services.node_definition import resolve_node_definition

# Bump this constant when the export schema changes in a breaking way.
# Add a corresponding _deserialize_v<N> method and update the dispatch table.
EXPORT_SCHEMA_VERSION = 1


class AgentConfigSerializer:
    """Serialization layer for agent export / import.

    Responsibilities
    ----------------
    - Produce deterministic, schema-versioned export payloads from ORM objects.
    - Parse and validate import payloads, creating the corresponding ORM objects.
    - Dispatch deserialization by schema_version for forward extensibility.

    This class has no dependency on AgentService or AgentVersionService and
    must not be called from within those classes.
    """

    @staticmethod
    def serialize(agent: Agent, version: AgentVersion) -> dict:
        """Convert a version (with its graph pre-loaded) into a portable payload.

        Edges are stored by node *name* rather than database ID so that the
        payload is valid in any environment where the agent is imported.
        """
        node_name_by_id = {node.id: node.name for node in version.nodes}

        nodes = [
            {
                "name": node.name,
                "type": node.type.value,
                "subtype": node.subtype.value,
                "config": dict(node.config or {}),
                "position_x": node.position_x,
                "position_y": node.position_y,
            }
            for node in sorted(version.nodes, key=lambda n: n.id)
        ]

        edges = [
            {
                "source_node_name": node_name_by_id[edge.source_node_id],
                "target_node_name": node_name_by_id[edge.target_node_id],
                "edge_type": edge.edge_type.value,
                "condition_config": dict(edge.condition_config or {}),
                "label": edge.label,
            }
            for edge in sorted(version.edges, key=lambda e: e.id)
            if edge.source_node_id in node_name_by_id
            and edge.target_node_id in node_name_by_id
        ]

        return {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "agent": {
                "name": agent.name,
                "description": agent.description,
            },
            "version": {
                "version_number": version.version_number,
                "entry_node": version.entry_node,
                "exit_nodes": list(version.exit_nodes or []),
                "state_schema": dict(version.state_schema or {}),
            },
            "nodes": nodes,
            "edges": edges,
        }

    @classmethod
    def deserialize(cls, data: dict, db: Session) -> Agent:
        """Parse an export payload and persist a new agent with its initial version.

        Returns the newly created Agent. Raises ValidationError on invalid input.
        Dispatches to the correct handler based on schema_version.
        """
        try:
            schema_version = int(data.get("schema_version") or 1)
        except (TypeError, ValueError):
            raise ValidationError("schema_version must be an integer")

        handlers = {
            1: cls._deserialize_v1,
        }
        handler = handlers.get(schema_version)
        if handler is None:
            raise ValidationError(
                f"Unsupported schema_version '{schema_version}'. "
                f"Supported versions: {sorted(handlers)}"
            )
        return handler(data, db)

    @staticmethod
    def _deserialize_v1(data: dict, db: Session) -> Agent:
        agent_data = data.get("agent") or {}
        version_data = data.get("version") or {}

        name = str(agent_data.get("name") or "").strip()
        if not name:
            raise ValidationError("agent.name is required")

        agent = Agent(
            name=name,
            description=agent_data.get("description") or None,
            status=AgentStatus.draft,
        )
        db.add(agent)
        db.flush()

        version = AgentVersion(
            agent_id=agent.id,
            version_number=1,
            entry_node=version_data.get("entry_node"),
            exit_nodes=list(version_data.get("exit_nodes") or []),
            state_schema=dict(version_data.get("state_schema") or {}),
        )
        db.add(version)
        db.flush()

        node_name_to_id: dict[str, int] = {}
        for raw_node in data.get("nodes") or []:
            node_name = str(raw_node.get("name") or "").strip()
            if not node_name:
                raise ValidationError("Every node must have a non-empty name")
            try:
                node_type, node_subtype, node_config = resolve_node_definition(
                    raw_node.get("type"),
                    raw_node.get("subtype"),
                    raw_node.get("config"),
                )
            except ValueError as exc:
                raise ValidationError(f"Invalid node '{node_name}': {exc}") from exc

            node = Node(
                agent_id=agent.id,
                version_id=version.id,
                name=node_name,
                type=node_type,
                subtype=node_subtype,
                config=node_config,
                position_x=float(raw_node.get("position_x") or 0.0),
                position_y=float(raw_node.get("position_y") or 0.0),
            )
            db.add(node)
            db.flush()
            node_name_to_id[node_name] = node.id

        for raw_edge in data.get("edges") or []:
            src_name = raw_edge.get("source_node_name")
            tgt_name = raw_edge.get("target_node_name")
            src_id = node_name_to_id.get(src_name)
            tgt_id = node_name_to_id.get(tgt_name)
            if src_id is None or tgt_id is None:
                raise ValidationError(
                    f"Edge references unknown node(s): "
                    f"source='{src_name}', target='{tgt_name}'"
                )
            try:
                edge_type = EdgeType(raw_edge.get("edge_type") or EdgeType.direct.value)
            except ValueError:
                raise ValidationError(
                    f"Unknown edge_type: '{raw_edge.get('edge_type')}'"
                )

            db.add(Edge(
                agent_id=agent.id,
                version_id=version.id,
                source_node_id=src_id,
                target_node_id=tgt_id,
                edge_type=edge_type,
                condition_config=dict(raw_edge.get("condition_config") or {}),
                label=raw_edge.get("label"),
            ))

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValidationError(f"Failed to import agent: {exc.orig}") from exc

        db.refresh(agent)
        return agent
