"""Parse JSON Schema files into intermediate Java model representations."""

from __future__ import annotations

import json
from typing import Any

from .models import (
    JavaClass,
    JavaEnum,
    JavaEnumValue,
    JavaField,
    JavaFieldConstraint,
    GeneratorConfig,
)
from .utils import (
    JSON_FORMAT_MAP,
    JSON_TYPE_MAP,
    to_camel_case,
    to_pascal_case,
    to_upper_snake_case,
)


def parse_json_schema(
    schema_content: str, config: GeneratorConfig
) -> tuple[list[JavaClass], list[JavaEnum]]:
    """Parse JSON Schema content and return Java classes and enums."""
    schema = json.loads(schema_content)
    classes: list[JavaClass] = []
    enums: list[JavaEnum] = []
    definitions: dict[str, Any] = {}
    # Track definitions currently being parsed to prevent circular recursion
    in_progress: set[str] = set()

    # Collect definitions / $defs
    definitions.update(schema.get("definitions", {}))
    definitions.update(schema.get("$defs", {}))

    # Parse all definitions first
    for def_name, def_schema in definitions.items():
        _parse_definition(def_name, def_schema, config, classes, enums, definitions, in_progress)

    # Parse root schema if it defines a type
    root_title = schema.get("title", "Root")
    if schema.get("type") == "object" or "properties" in schema:
        _parse_object_schema(root_title, schema, config, classes, enums, definitions, in_progress)
    elif "enum" in schema:
        enum = _parse_enum_schema(root_title, schema, config)
        enums.append(enum)

    return classes, enums


def _parse_definition(
    name: str,
    schema: dict[str, Any],
    config: GeneratorConfig,
    classes: list[JavaClass],
    enums: list[JavaEnum],
    definitions: dict[str, Any],
    in_progress: set[str],
):
    """Parse a single definition from the schema."""
    if "enum" in schema:
        enum = _parse_enum_schema(name, schema, config)
        enums.append(enum)
    elif schema.get("type") == "object" or "properties" in schema:
        _parse_object_schema(name, schema, config, classes, enums, definitions, in_progress)
    elif "allOf" in schema:
        _parse_allof_schema(name, schema, config, classes, enums, definitions, in_progress)
    elif "oneOf" in schema or "anyOf" in schema:
        # Generate a marker class with an Object field for now
        _parse_object_schema(name, schema, config, classes, enums, definitions, in_progress)


def _parse_enum_schema(
    name: str, schema: dict[str, Any], config: GeneratorConfig
) -> JavaEnum:
    """Parse a JSON Schema enum into a JavaEnum."""
    enum_name = to_pascal_case(name)
    values = []
    for v in schema.get("enum", []):
        str_val = str(v)
        constant = to_upper_snake_case(str_val)
        values.append(JavaEnumValue(name=constant, value=str_val))

    return JavaEnum(
        name=enum_name,
        package_name=config.package_name,
        values=values,
        description=schema.get("description"),
    )


def _parse_object_schema(
    name: str,
    schema: dict[str, Any],
    config: GeneratorConfig,
    classes: list[JavaClass],
    enums: list[JavaEnum],
    definitions: dict[str, Any],
    in_progress: set[str],
):
    """Parse a JSON Schema object into a JavaClass."""
    class_name = to_pascal_case(name)

    # Avoid duplicates and circular recursion
    if any(c.name == class_name for c in classes) or class_name in in_progress:
        return

    in_progress.add(class_name)

    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    fields: list[JavaField] = []
    inner_enums: list[JavaEnum] = []

    for prop_name, prop_schema in properties.items():
        field = _parse_property(
            prop_name,
            prop_schema,
            prop_name in required_fields,
            config,
            classes,
            enums,
            definitions,
            class_name,
            inner_enums,
            in_progress,
        )
        fields.append(field)

    # Handle additionalProperties as a Map field
    additional = schema.get("additionalProperties")
    if isinstance(additional, dict) and additional.get("type"):
        value_type = _resolve_java_type(additional, definitions)
        fields.append(
            JavaField(
                name="additionalProperties",
                java_type=f"java.util.Map<String, {value_type}>",
                json_property_name="additionalProperties",
            )
        )

    java_class = JavaClass(
        name=class_name,
        package_name=config.package_name,
        fields=fields,
        description=schema.get("description"),
        inner_enums=inner_enums,
    )
    classes.append(java_class)
    in_progress.discard(class_name)


def _parse_allof_schema(
    name: str,
    schema: dict[str, Any],
    config: GeneratorConfig,
    classes: list[JavaClass],
    enums: list[JavaEnum],
    definitions: dict[str, Any],
    in_progress: set[str],
):
    """Parse allOf schema (typically used for inheritance)."""
    class_name = to_pascal_case(name)

    if any(c.name == class_name for c in classes) or class_name in in_progress:
        return

    in_progress.add(class_name)

    parent_class = None
    merged_properties: dict[str, Any] = {}
    merged_required: list[str] = []

    for sub_schema in schema.get("allOf", []):
        ref = sub_schema.get("$ref")
        if ref:
            ref_name = ref.rsplit("/", 1)[-1]
            parent_class = to_pascal_case(ref_name)
            # Ensure parent is parsed
            if ref_name in definitions and not any(c.name == parent_class for c in classes):
                _parse_definition(ref_name, definitions[ref_name], config, classes, enums, definitions, in_progress)
        else:
            merged_properties.update(sub_schema.get("properties", {}))
            merged_required.extend(sub_schema.get("required", []))

    required_set = set(merged_required)
    fields: list[JavaField] = []
    inner_enums: list[JavaEnum] = []

    for prop_name, prop_schema in merged_properties.items():
        field = _parse_property(
            prop_name,
            prop_schema,
            prop_name in required_set,
            config,
            classes,
            enums,
            definitions,
            class_name,
            inner_enums,
            in_progress,
        )
        fields.append(field)

    java_class = JavaClass(
        name=class_name,
        package_name=config.package_name,
        fields=fields,
        parent_class=parent_class,
        description=schema.get("description"),
        inner_enums=inner_enums,
    )
    classes.append(java_class)
    in_progress.discard(class_name)


def _parse_property(
    prop_name: str,
    prop_schema: dict[str, Any],
    is_required: bool,
    config: GeneratorConfig,
    classes: list[JavaClass],
    enums: list[JavaEnum],
    definitions: dict[str, Any],
    owner_class: str,
    inner_enums: list[JavaEnum],
    in_progress: set[str],
) -> JavaField:
    """Parse a single JSON Schema property into a JavaField."""
    field_name = to_camel_case(prop_name)
    json_property_name = prop_name if prop_name != field_name else None

    # Handle $ref
    ref = prop_schema.get("$ref")
    if ref:
        ref_name = ref.rsplit("/", 1)[-1]
        ref_schema = definitions.get(ref_name, {})
        if "enum" in ref_schema:
            java_type = to_pascal_case(ref_name)
            return JavaField(
                name=field_name,
                java_type=java_type,
                required=is_required,
                constraints=JavaFieldConstraint(not_null=is_required, valid=True),
                json_property_name=json_property_name,
                is_enum_type=True,
            )
        else:
            java_type = to_pascal_case(ref_name)
            # Ensure referenced type is parsed
            if ref_name in definitions and not any(c.name == java_type for c in classes):
                _parse_definition(ref_name, definitions[ref_name], config, classes, enums, definitions, in_progress)
            return JavaField(
                name=field_name,
                java_type=java_type,
                required=is_required,
                constraints=JavaFieldConstraint(not_null=is_required, valid=True),
                json_property_name=json_property_name,
            )

    # Handle enum inline
    if "enum" in prop_schema:
        enum_name = to_pascal_case(prop_name)
        inner_enum = _parse_enum_schema(prop_name, prop_schema, config)
        inner_enum.name = enum_name
        inner_enums.append(inner_enum)
        return JavaField(
            name=field_name,
            java_type=enum_name,
            required=is_required,
            constraints=JavaFieldConstraint(not_null=is_required),
            json_property_name=json_property_name,
            is_enum_type=True,
        )

    prop_type = prop_schema.get("type", "object")

    # Handle array
    if prop_type == "array":
        items = prop_schema.get("items", {})
        item_type = _resolve_java_type(items, definitions)

        # If items is a $ref to a definition, ensure it's parsed
        item_ref = items.get("$ref")
        if item_ref:
            item_ref_name = item_ref.rsplit("/", 1)[-1]
            if item_ref_name in definitions:
                _parse_definition(item_ref_name, definitions[item_ref_name], config, classes, enums, definitions, in_progress)

        # If items has inline enum
        if "enum" in items:
            enum_name = to_pascal_case(prop_name) + "Item"
            inner_enum = _parse_enum_schema(prop_name + "Item", items, config)
            inner_enum.name = enum_name
            inner_enums.append(inner_enum)
            item_type = enum_name

        # If items has inline object
        if items.get("type") == "object" or "properties" in items:
            item_class_name = to_pascal_case(prop_name) + "Item"
            items_with_title = {**items, "title": item_class_name}
            _parse_object_schema(item_class_name, items_with_title, config, classes, enums, definitions, in_progress)
            item_type = item_class_name

        constraints = _extract_constraints(prop_schema, "array", is_required)
        if prop_schema.get("minItems") is not None:
            constraints.size_min = prop_schema["minItems"]
        if prop_schema.get("maxItems") is not None:
            constraints.size_max = prop_schema["maxItems"]

        return JavaField(
            name=field_name,
            java_type=f"java.util.List<{item_type}>",
            required=is_required,
            constraints=constraints,
            json_property_name=json_property_name,
            is_list=True,
            list_item_type=item_type,
        )

    # Handle nested object
    if prop_type == "object" and "properties" in prop_schema:
        nested_class_name = to_pascal_case(prop_name)
        _parse_object_schema(nested_class_name, prop_schema, config, classes, enums, definitions, in_progress)
        constraints = JavaFieldConstraint(not_null=is_required, valid=True)
        return JavaField(
            name=field_name,
            java_type=nested_class_name,
            required=is_required,
            constraints=constraints,
            json_property_name=json_property_name,
        )

    # Simple types
    java_type = _resolve_java_type(prop_schema, definitions)
    constraints = _extract_constraints(prop_schema, java_type, is_required)

    return JavaField(
        name=field_name,
        java_type=java_type,
        required=is_required,
        constraints=constraints,
        json_property_name=json_property_name,
        description=prop_schema.get("description"),
    )


def _resolve_java_type(schema: dict[str, Any], definitions: dict[str, Any]) -> str:
    """Resolve a JSON Schema type to a Java type."""
    ref = schema.get("$ref")
    if ref:
        ref_name = ref.rsplit("/", 1)[-1]
        return to_pascal_case(ref_name)

    schema_type = schema.get("type", "object")
    schema_format = schema.get("format")

    # Check format first
    if schema_format and schema_format in JSON_FORMAT_MAP:
        return JSON_FORMAT_MAP[schema_format]

    if schema_type == "string":
        if schema_format == "email":
            return "String"  # but we'll add @Email constraint
        return "String"
    elif schema_type == "integer":
        if schema_format == "int32":
            return "Integer"
        return "Long"
    elif schema_type == "number":
        if schema_format == "float":
            return "Float"
        if schema_format == "double":
            return "Double"
        return "java.math.BigDecimal"
    elif schema_type == "boolean":
        return "Boolean"
    elif schema_type == "object":
        return "Object"
    elif isinstance(schema_type, list):
        # Handle nullable types like ["string", "null"]
        non_null = [t for t in schema_type if t != "null"]
        if non_null:
            return _resolve_java_type({"type": non_null[0], "format": schema.get("format")}, definitions)
        return "Object"

    return JSON_TYPE_MAP.get(str(schema_type), "Object")


def _extract_constraints(
    schema: dict[str, Any], java_type: str, is_required: bool
) -> JavaFieldConstraint:
    """Extract validation constraints from JSON Schema property."""
    constraints = JavaFieldConstraint(not_null=is_required)

    if is_required and java_type == "String":
        constraints.not_blank = True

    # String constraints
    if "minLength" in schema:
        constraints.min_length = schema["minLength"]
    if "maxLength" in schema:
        constraints.max_length = schema["maxLength"]
    if "pattern" in schema:
        constraints.pattern = schema["pattern"]

    # Numeric constraints
    if "minimum" in schema:
        constraints.min_value = str(schema["minimum"])
        if schema.get("exclusiveMinimum") is True:
            constraints.min_exclusive = True
    if "maximum" in schema:
        constraints.max_value = str(schema["maximum"])
        if schema.get("exclusiveMaximum") is True:
            constraints.max_exclusive = True

    # Draft 6+ exclusiveMinimum/Maximum as numbers
    if isinstance(schema.get("exclusiveMinimum"), (int, float)):
        constraints.min_value = str(schema["exclusiveMinimum"])
        constraints.min_exclusive = True
    if isinstance(schema.get("exclusiveMaximum"), (int, float)):
        constraints.max_value = str(schema["exclusiveMaximum"])
        constraints.max_exclusive = True

    # Email format
    if schema.get("format") == "email":
        constraints.email = True

    return constraints
