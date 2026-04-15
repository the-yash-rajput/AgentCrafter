import unittest

from services.node_definition import get_node_definitions, normalize_node_type, resolve_node_definition
from models import NodeCategory, NodeSubtype, NodeType
from services.runtime.nodes.factory import NodeRunnerFactory


class NodeDefinitionTests(unittest.TestCase):
    def test_normalize_node_type_accepts_llm_alias(self) -> None:
        self.assertEqual(normalize_node_type("llm"), NodeType.llm_call)

    def test_resolve_node_definition_infers_functional_subtype_from_config(self) -> None:
        node_type, subtype, config = resolve_node_definition(
            "functional",
            None,
            {"function_type": "agent_call"},
        )

        self.assertEqual(node_type, NodeType.functional)
        self.assertEqual(subtype, NodeSubtype.agent_call)
        self.assertEqual(config["function_type"], NodeSubtype.agent_call.value)

    def test_resolve_node_definition_defaults_llm_subtype(self) -> None:
        node_type, subtype, config = resolve_node_definition("llm_call", None, {"provider": "azure_openai"})

        self.assertEqual(node_type, NodeType.llm_call)
        self.assertEqual(subtype, NodeSubtype.chat)
        self.assertEqual(config["provider"], "azure_openai")
        self.assertEqual(config["llm_type"], NodeSubtype.chat.value)

    def test_resolve_node_definition_promotes_legacy_agent_runtime_to_llm_agent(self) -> None:
        node_type, subtype, config = resolve_node_definition(
            "llm_call",
            NodeSubtype.chat,
            {"provider": "azure_openai", "llm_runtime": "agent"},
        )

        self.assertEqual(node_type, NodeType.llm_call)
        self.assertEqual(subtype, NodeSubtype.llm_agent)
        self.assertEqual(config["llm_type"], NodeSubtype.llm_agent.value)
        self.assertNotIn("llm_runtime", config)

    def test_node_definitions_catalog_excludes_data_transform(self) -> None:
        definitions = get_node_definitions()
        subtypes = {definition.subtype for definition in definitions}
        categories = {definition.category for definition in definitions}
        visibility = {definition.subtype: definition.show_in_frontend for definition in definitions}

        self.assertNotIn("data_transform", {subtype.value for subtype in subtypes})
        self.assertNotIn(NodeSubtype.api_call, subtypes)
        self.assertIn(NodeSubtype.python_inline, subtypes)
        self.assertIn(NodeSubtype.agent_call, subtypes)
        self.assertIn(NodeSubtype.llm_agent, subtypes)
        self.assertIn(NodeSubtype.api, subtypes)
        self.assertIn(NodeSubtype.rabbitmq_message, subtypes)
        self.assertIn(NodeSubtype.kafka, subtypes)
        self.assertIn(NodeCategory.llm, categories)
        self.assertIn(NodeCategory.functional, categories)
        self.assertIn(NodeCategory.communication, categories)
        self.assertTrue(all(isinstance(is_visible, bool) for is_visible in visibility.values()))
        self.assertFalse(visibility[NodeSubtype.kafka])
        self.assertTrue(visibility[NodeSubtype.api])

    def test_node_runner_factory_builds_llm_runner(self) -> None:
        runner = NodeRunnerFactory().build(
            node_type="llm_call",
            subtype=NodeSubtype.llm_agent,
            config={},
        )

        self.assertTrue(callable(runner))


if __name__ == "__main__":
    unittest.main()
