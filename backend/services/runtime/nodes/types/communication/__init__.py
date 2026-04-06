from __future__ import annotations

from models import NodeSubtype
from type_defs import JSONMapping, NodeRunner


def build_communication_node(
    subtype: NodeSubtype,
    config: JSONMapping,
) -> NodeRunner:
    if subtype == NodeSubtype.rabbitmq_message:
        from services.runtime.nodes.types.communication.rabbitmq_message import build_rabbitmq_message_node

        return build_rabbitmq_message_node(config)

    if subtype == NodeSubtype.kafka:
        from services.runtime.nodes.types.communication.kafka import build_kafka_node

        return build_kafka_node(config)

    if subtype == NodeSubtype.api:
        from services.runtime.nodes.types.communication.api import build_communication_api_node

        return build_communication_api_node(config)

    raise ValueError(f"Unsupported communication node subtype '{subtype}'")
