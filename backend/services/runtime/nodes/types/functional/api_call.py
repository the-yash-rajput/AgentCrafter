from __future__ import annotations

import json

from jinja2 import Template
from type_defs import JSONMapping, NodeRunner, StatePayload


def build_api_call_node(config: JSONMapping) -> NodeRunner:
    api_cfg = config.get("api_call", {})

    def api_node(state: StatePayload) -> StatePayload:
        url_template = Template(api_cfg.get("url", ""))
        url = url_template.render(**state)
        method = api_cfg.get("method", "GET").upper()
        headers = api_cfg.get("headers", {})
        body_template_str = api_cfg.get("body_template", "")
        output_key = api_cfg.get("output_key", "api_result")

        body = None
        if body_template_str:
            body = Template(body_template_str).render(**state)
            try:
                body = json.loads(body)
            except Exception:
                pass

        try:
            import httpx

            with httpx.Client() as client:
                response = client.request(method, url, headers=headers, json=body)
                response.raise_for_status()
                return {**state, output_key: response.json()}
        except Exception as exc:
            return {**state, "_error": str(exc)}

    return api_node
