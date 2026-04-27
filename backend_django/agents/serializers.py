"""
DRF serializers for the agents app.

These replace the Pydantic schemas in schemas/schemas.py at the HTTP boundary:
  - Read serializers (ModelSerializer) convert SQLAlchemy model instances
    returned by the service layer into JSON for responses.
  - Write serializers (Serializer) validate incoming request data and build
    Pydantic payloads to pass to the service layer.

The service layer still uses Pydantic internally — we build AgentCreate /
NodeCreate / etc. from DRF validated_data before calling services, so no
service code needs to change.

Response field names exactly match the existing FastAPI responses to preserve
frontend compatibility.
"""
import enum

from rest_framework import serializers


# ── Helpers ───────────────────────────────────────────────────────────────────

class _SAModelSerializer(serializers.Serializer):
    """
    Base class for read serializers that receive SQLAlchemy ORM instances
    (not Django ORM instances). DRF's ModelSerializer requires Django models,
    so we use plain Serializer with explicit fields instead.

    Unwraps enum instances to their .value before DRF field serialization so
    that str(enum_member) — which returns "ClassName.member" in Python 3.11+
    — never reaches the output.
    """

    def to_representation(self, instance):
        # Unwrap any enum attributes before the normal DRF field loop runs.
        class _EnumProxy:
            """Thin wrapper that exposes .value on enum attributes."""
            def __init__(self, obj):
                object.__setattr__(self, "_obj", obj)

            def __getattr__(self, name):
                val = getattr(object.__getattribute__(self, "_obj"), name)
                if isinstance(val, enum.Enum):
                    return val.value
                return val

        return super().to_representation(_EnumProxy(instance))


# ── Node read serializer ──────────────────────────────────────────────────────

class NodeResponseSerializer(_SAModelSerializer):
    id = serializers.IntegerField()
    agent_id = serializers.IntegerField()
    version_id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.CharField()       # NodeType enum value
    subtype = serializers.CharField()    # NodeSubtype enum value
    config = serializers.DictField()
    position_x = serializers.FloatField()
    position_y = serializers.FloatField()
    created_at = serializers.DateTimeField()


# ── Edge read serializer ──────────────────────────────────────────────────────

class EdgeResponseSerializer(_SAModelSerializer):
    id = serializers.IntegerField()
    agent_id = serializers.IntegerField()
    version_id = serializers.IntegerField()
    source_node_id = serializers.IntegerField()
    target_node_id = serializers.IntegerField()
    edge_type = serializers.CharField()
    condition_config = serializers.DictField()
    label = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


# ── AgentVersion read serializer ──────────────────────────────────────────────

class AgentVersionResponseSerializer(_SAModelSerializer):
    id = serializers.IntegerField()
    agent_id = serializers.IntegerField()
    version_number = serializers.IntegerField()
    entry_node = serializers.CharField(allow_null=True)
    exit_nodes = serializers.ListField(child=serializers.CharField())
    state_schema = serializers.DictField()
    created_from_version_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()


class AgentVersionWithGraphSerializer(AgentVersionResponseSerializer):
    nodes = NodeResponseSerializer(many=True)
    edges = EdgeResponseSerializer(many=True)


class VersionPatchSerializer(serializers.Serializer):
    """Validates PATCH /api/agents/{id}/versions/{vid} request body."""
    state_schema = serializers.DictField(required=False)
    entry_node = serializers.CharField(required=False, allow_null=True)
    exit_nodes = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True)


# ── Agent read serializers ────────────────────────────────────────────────────

class AgentResponseSerializer(_SAModelSerializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class AgentWithGraphSerializer(AgentResponseSerializer):
    nodes = NodeResponseSerializer(many=True)
    edges = EdgeResponseSerializer(many=True)


class AgentListResponseSerializer(_SAModelSerializer):
    """Minimal agent representation used for the list endpoint."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    versions = AgentVersionResponseSerializer(many=True)


# ── Agent write serializers ───────────────────────────────────────────────────

class AgentCreateSerializer(serializers.Serializer):
    """Validates POST /api/agents request body."""
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_null=True, default=None)


class AgentUpdateSerializer(serializers.Serializer):
    """Validates PUT /api/agents/{id} request body (all fields optional)."""
    name = serializers.CharField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=["draft", "active", "archived"], required=False, allow_null=True
    )


# ── Node write serializers ────────────────────────────────────────────────────

class NodeCreateSerializer(serializers.Serializer):
    """
    Validates POST /api/agents/{id}/nodes request body.

    The model_validator logic from the Pydantic NodeCreate schema
    (normalize type/subtype, resolve node definition) runs in validate().
    """
    name = serializers.CharField(max_length=255)
    type = serializers.CharField()
    subtype = serializers.CharField(required=False, allow_null=True, default=None)
    config = serializers.DictField(required=False, default=dict)
    position_x = serializers.FloatField(required=False, default=0.0)
    position_y = serializers.FloatField(required=False, default=0.0)

    def validate(self, attrs):
        # Replicate NodeCreate's @field_validator and @model_validator logic
        from services.node_definition import (
            normalize_node_subtype,
            normalize_node_type,
            resolve_node_definition,
        )
        attrs["type"] = normalize_node_type(attrs["type"])
        attrs["subtype"] = normalize_node_subtype(attrs.get("subtype"))
        resolved_type, resolved_subtype, resolved_config = resolve_node_definition(
            attrs["type"], attrs["subtype"], attrs["config"]
        )
        attrs["type"] = resolved_type
        attrs["subtype"] = resolved_subtype
        attrs["config"] = resolved_config
        return attrs


class NodeUpdateSerializer(serializers.Serializer):
    """Validates PUT /api/nodes/{id} request body."""
    name = serializers.CharField(required=False, allow_null=True)
    type = serializers.CharField(required=False, allow_null=True)
    subtype = serializers.CharField(required=False, allow_null=True)
    config = serializers.DictField(required=False, allow_null=True)
    position_x = serializers.FloatField(required=False, allow_null=True)
    position_y = serializers.FloatField(required=False, allow_null=True)

    def validate_type(self, value):
        if value is None:
            return value
        from services.node_definition import normalize_node_type
        return normalize_node_type(value)

    def validate_subtype(self, value):
        from services.node_definition import normalize_node_subtype
        return normalize_node_subtype(value)


# ── Edge write serializers ────────────────────────────────────────────────────

class EdgeCreateSerializer(serializers.Serializer):
    """Validates POST /api/agents/{id}/edges request body."""
    source_node_id = serializers.IntegerField()
    target_node_id = serializers.IntegerField()
    edge_type = serializers.ChoiceField(
        choices=["direct", "conditional"], default="direct"
    )
    condition_config = serializers.DictField(required=False, default=dict)
    label = serializers.CharField(required=False, allow_null=True, default=None)


class EdgeUpdateSerializer(serializers.Serializer):
    """Validates PUT /api/edges/{id} request body."""
    source_node_id = serializers.IntegerField(required=False, allow_null=True)
    target_node_id = serializers.IntegerField(required=False, allow_null=True)
    edge_type = serializers.ChoiceField(
        choices=["direct", "conditional"], required=False, allow_null=True
    )
    condition_config = serializers.DictField(required=False, allow_null=True)
    label = serializers.CharField(required=False, allow_null=True)


# ── Node definition read serializer ──────────────────────────────────────────

class NodeDefinitionResponseSerializer(_SAModelSerializer):
    """Serializes NodeDefinition objects returned by NodeService."""
    type = serializers.CharField()
    subtype = serializers.CharField()
    category = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    show_in_frontend = serializers.BooleanField()
    default_config = serializers.DictField()


# ── Export / Import serializers ───────────────────────────────────────────────

class AgentExportPayloadSerializer(serializers.Serializer):
    """Serializes the AgentExportPayload returned by AgentConfigSerializer."""
    schema_version = serializers.IntegerField()
    agent = serializers.DictField()
    version = serializers.DictField()
    nodes = serializers.ListField(child=serializers.DictField())
    edges = serializers.ListField(child=serializers.DictField())
