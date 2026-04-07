from __future__ import annotations

import json

from jinja2 import Template

from type_defs import JSONMapping, StatePayload


def render_template(template_value: str, state: StatePayload) -> str:
    return Template(str(template_value or "")).render(**state)


def parse_template_payload(template_value: str, state: StatePayload):
    rendered = render_template(template_value, state)
    try:
        return json.loads(rendered)
    except Exception:
        return rendered


def no_op_transport_result(
    *,
    subtype: str,
    target: str,
    payload,
    output_key: str,
    state: StatePayload,
) -> StatePayload:
    # Placeholder transport node until broker-backed delivery is implemented.
    return {
        **state,
        output_key: {
            "status": "queued_locally",
            "transport": subtype,
            "target": target,
            "payload": payload,
        },
    }
