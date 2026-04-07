from __future__ import annotations

from type_defs import JSONMapping, NodeRunner, StatePayload
from services.runtime.nodes.types.communication.common import no_op_transport_result, parse_template_payload, render_template


def build_kafka_node(config: JSONMapping) -> NodeRunner:
    kafka_cfg = config.get("kafka", {})

    def kafka_node(state: StatePayload) -> StatePayload:
        topic = str(kafka_cfg.get("topic") or "").strip() or "kafka"
        key = render_template(kafka_cfg.get("key_template", ""), state)
        payload = parse_template_payload(kafka_cfg.get("payload_template", ""), state)
        output_key = str(kafka_cfg.get("output_key") or "kafka_result").strip() or "kafka_result"
        target = topic if not key else f"{topic}:{key}"

        return no_op_transport_result(
            subtype="kafka",
            target=target,
            payload=payload,
            output_key=output_key,
            state=state,
        )

    return kafka_node
