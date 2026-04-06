from __future__ import annotations

from type_defs import JSONMapping, NodeRunner, StatePayload
from services.runtime.nodes.types.communication.common import no_op_transport_result, parse_template_payload


def build_rabbitmq_message_node(config: JSONMapping) -> NodeRunner:
    rabbitmq_cfg = config.get("rabbitmq_message", {})

    def rabbitmq_message_node(state: StatePayload) -> StatePayload:
        exchange = str(rabbitmq_cfg.get("exchange") or "").strip()
        routing_key = str(rabbitmq_cfg.get("routing_key") or "").strip()
        queue = str(rabbitmq_cfg.get("queue") or "").strip()
        payload = parse_template_payload(rabbitmq_cfg.get("payload_template", ""), state)
        output_key = str(rabbitmq_cfg.get("output_key") or "rabbitmq_result").strip() or "rabbitmq_result"
        target = routing_key or queue or exchange or "rabbitmq"

        return no_op_transport_result(
            subtype="rabbitmq_message",
            target=target,
            payload=payload,
            output_key=output_key,
            state=state,
        )

    return rabbitmq_message_node
