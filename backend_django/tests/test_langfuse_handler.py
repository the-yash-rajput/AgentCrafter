import unittest
from types import SimpleNamespace
from unittest.mock import patch

from base.handlers.langfuse_handler import langfuse_callback_handler


class LangfuseHandlerTests(unittest.TestCase):
    def test_uses_legacy_langchain_import_when_available(self) -> None:
        class LegacyCallbackHandler:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        def fake_import_module(name):
            if name == "langfuse.langchain":
                return SimpleNamespace(CallbackHandler=LegacyCallbackHandler)
            raise AssertionError(f"Unexpected import: {name}")

        with patch(
            "base.handlers.langfuse_handler.LangfuseClientWrapper.get_langfuse_client",
            return_value=object(),
        ), patch(
            "base.handlers.langfuse_handler.import_module",
            side_effect=fake_import_module,
        ):
            handler = langfuse_callback_handler(trace_context={"trace_id": "abc"})

        self.assertIsInstance(handler, LegacyCallbackHandler)
        self.assertEqual(handler.kwargs, {"trace_context": {"trace_id": "abc"}})

    def test_falls_back_to_callback_import_when_legacy_module_missing(self) -> None:
        class ModernCallbackHandler:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        def fake_import_module(name):
            if name == "langfuse.langchain":
                raise ModuleNotFoundError("No module named 'langfuse.langchain'")
            if name == "langfuse.callback":
                return SimpleNamespace(CallbackHandler=ModernCallbackHandler)
            raise AssertionError(f"Unexpected import: {name}")

        with patch(
            "base.handlers.langfuse_handler.LangfuseClientWrapper.get_langfuse_client",
            return_value=object(),
        ), patch(
            "base.handlers.langfuse_handler.import_module",
            side_effect=fake_import_module,
        ):
            handler = langfuse_callback_handler(trace_context={"trace_id": "abc"})

        self.assertIsInstance(handler, ModernCallbackHandler)
        self.assertEqual(handler.kwargs, {"trace_context": {"trace_id": "abc"}})

    def test_returns_none_when_no_supported_callback_import_exists(self) -> None:
        with patch(
            "base.handlers.langfuse_handler.LangfuseClientWrapper.get_langfuse_client",
            return_value=object(),
        ), patch(
            "base.handlers.langfuse_handler.import_module",
            side_effect=ModuleNotFoundError("missing"),
        ):
            handler = langfuse_callback_handler()

        self.assertIsNone(handler)
