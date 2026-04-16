from __future__ import annotations

import json

from jinja2 import Template

from type_defs import JSONMapping, NodeRunner, StatePayload


def build_communication_api_node(config: JSONMapping) -> NodeRunner:
    api_cfg = config.get("api", {})

    def api_node(state: StatePayload) -> StatePayload:
        url_template = Template(api_cfg.get("url", ""))
        url = url_template.render(**state)
        method = str(api_cfg.get("method", "POST")).upper()
        headers = api_cfg.get("headers", {})
        body_template_str = api_cfg.get("body_template", "")
        output_key = str(api_cfg.get("output_key") or "api_result").strip() or "api_result"

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
                try:
                    payload = response.json()
                except Exception:
                    payload = response.text
                return {**state, output_key: payload}
        except Exception as exc:
            return {**state, "_error": str(exc)}

    return api_node
