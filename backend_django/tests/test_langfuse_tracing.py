import unittest
from unittest.mock import patch

from services.runtime import langfuse_tracing as tracing_module
from services.runtime.nodes.types.llm import common as llm_common_module


class _FakeScope:
    def __init__(self, observation) -> None:
        self.observation = observation
        self.exited = False

    def __enter__(self):
        return self.observation

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        self.exited = True
        self.observation.end()


class _FakeObservation:
    _counter = 0

    def __init__(self, name: str, *, parent=None, as_type: str = "chain", trace_id: str = "trace-1") -> None:
        type(self)._counter += 1
        self.name = name
        self.parent = parent
        self.as_type = as_type
        self.trace_id = trace_id
        self.id = f"span-{type(self)._counter}"
        self.children = []
        self.updates = []
        self.created = []
        self.ended = False

    def start_as_current_observation(self, **kwargs):
        child = _FakeObservation(
            kwargs["name"],
            parent=self,
            as_type=kwargs.get("as_type", "span"),
            trace_id=self.trace_id,
        )
        child.created.append(kwargs)
        self.children.append(child)
        return _FakeScope(child)

    def start_observation(self, **kwargs):
        child = _FakeObservation(
            kwargs["name"],
            parent=self,
            as_type=kwargs.get("as_type", "span"),
            trace_id=self.trace_id,
        )
        child.created.append(kwargs)
        self.children.append(child)
        return child

    def update(self, **kwargs):
        self.updates.append(kwargs)
        return self

    def end(self):
        self.ended = True
        return self


class LangfuseTracingTests(unittest.TestCase):
    def test_nested_runtime_spans_follow_live_parent_chain(self) -> None:
        root = _FakeObservation("LangGraph")
        token = tracing_module.set_current_trace(root)
        self.addCleanup(tracing_module.reset_current_trace, token)

        outer_span, outer_scope = tracing_module.start_current_runtime_span("node")
        inner_span, inner_scope = tracing_module.start_current_runtime_span("model")

        self.assertIsNotNone(outer_span)
        self.assertIsNotNone(inner_span)
        self.assertIs(outer_span.parent, root)
        self.assertIs(inner_span.parent, outer_span)
        self.assertEqual(
            tracing_module.get_current_trace_context(),
            {"trace_id": root.trace_id, "parent_span_id": inner_span.id},
        )

        tracing_module.end_current_runtime_span(
            inner_span,
            inner_scope,
            output_payload={"status": "success"},
        )
        self.assertEqual(
            tracing_module.get_current_trace_context(),
            {"trace_id": root.trace_id, "parent_span_id": outer_span.id},
        )

        tracing_module.end_current_runtime_span(
            outer_span,
            outer_scope,
            output_payload={"status": "success"},
        )
        self.assertEqual(
            tracing_module.get_current_trace_context(),
            {"trace_id": root.trace_id, "parent_span_id": root.id},
        )

    def test_error_spans_capture_error_status_details(self) -> None:
        root = _FakeObservation("LangGraph")
        token = tracing_module.set_current_trace(root)
        self.addCleanup(tracing_module.reset_current_trace, token)

        span, scope = tracing_module.start_current_runtime_span("node")
        tracing_module.end_current_runtime_span(
            span,
            scope,
            output_payload={"status": "error", "error": "boom"},
        )

        self.assertTrue(span.ended)
        self.assertEqual(
            span.updates[-1],
            {
                "output": {"status": "error", "error": "boom"},
                "level": "ERROR",
                "status_message": "boom",
            },
        )

    def test_llm_generation_uses_current_observation_as_parent(self) -> None:
        root = _FakeObservation("LangGraph")
        token = tracing_module.set_current_trace(root)
        self.addCleanup(tracing_module.reset_current_trace, token)

        model_span, model_scope = tracing_module.start_current_runtime_span("model")
        tracing_module.log_llm_generation(
            name="llm_call",
            provider="azure_openai",
            model="gpt-4o",
            input_payload=[{"role": "user", "content": "hello"}],
            output_payload=[{"role": "assistant", "content": "world"}],
            metadata={"node_name": "chat-node"},
        )
        tracing_module.end_current_runtime_span(
            model_span,
            model_scope,
            output_payload={"status": "success"},
        )

        self.assertEqual(len(model_span.children), 1)
        generation = model_span.children[0]
        self.assertIs(generation.parent, model_span)
        self.assertEqual(generation.as_type, "generation")
        self.assertTrue(generation.ended)

    def test_resolve_langfuse_handler_prefers_current_trace_context(self) -> None:
        with patch.object(
            llm_common_module,
            "get_current_trace_context",
            return_value={"trace_id": "trace-1", "parent_span_id": "span-9"},
        ), patch.object(
            llm_common_module,
            "langfuse_callback_handler",
            return_value="scoped-handler",
        ) as callback_factory:
            handler = llm_common_module.resolve_langfuse_handler(
                {
                    "langfuse_handler": "shared-handler",
                    "langfuse_trace_context": {"trace_id": "trace-root", "parent_span_id": "span-root"},
                }
            )

        self.assertEqual(handler, "scoped-handler")
        callback_factory.assert_called_once_with(
            trace_context={"trace_id": "trace-1", "parent_span_id": "span-9"}
        )

    def test_resolve_langfuse_handler_reuses_shared_handler_without_active_trace_context(self) -> None:
        with patch.object(
            llm_common_module,
            "get_current_trace_context",
            return_value=None,
        ), patch.object(
            llm_common_module,
            "langfuse_callback_handler",
            side_effect=AssertionError("unexpected callback construction"),
        ):
            handler = llm_common_module.resolve_langfuse_handler(
                {"langfuse_handler": "shared-handler"}
            )

        self.assertEqual(handler, "shared-handler")


if __name__ == "__main__":
    unittest.main()
