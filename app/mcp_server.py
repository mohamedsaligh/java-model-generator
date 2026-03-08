"""MCP Server for Java Model Generator.

Exposes the Java model generation functionality as MCP tools
that can accept schema files and return generated Java source files.
"""

from __future__ import annotations

import base64
import io
import json
import zipfile
from typing import Any

from mcp.server.fastmcp import FastMCP

from .generator.base import generate_models, generate_to_zip
from .generator.models import GeneratorConfig, SchemaType

mcp = FastMCP(
    "Java Model Generator",
    instructions="Generate Java DTO models from XSD, JSON Schema with Lombok and Jakarta validation.",
    streamable_http_path="/",
)


@mcp.tool()
def generate_java_models(
    schema_content: str,
    schema_type: str = "json",
    package_name: str = "com.example.dto",
    use_lombok: bool = True,
    use_jakarta_validation: bool = True,
    use_builder: bool = True,
    serializable: bool = True,
    json_include_non_null: bool = True,
) -> str:
    """Generate Java DTO model classes from a schema definition.

    Accepts XSD or JSON Schema content and generates compilable Java classes
    with Lombok annotations, Jakarta validation constraints, and Jackson
    serialization support.

    Args:
        schema_content: The raw schema content (XSD XML or JSON Schema string).
        schema_type: Schema format - "xsd" or "json" (default: "json").
        package_name: Java package name for generated classes (default: "com.example.dto").
        use_lombok: Add Lombok annotations (@Data, @Builder, etc.) (default: True).
        use_jakarta_validation: Add Jakarta validation annotations (default: True).
        use_builder: Add Lombok @Builder annotation (default: True).
        serializable: Implement java.io.Serializable (default: True).
        json_include_non_null: Add @JsonInclude(NON_NULL) (default: True).

    Returns:
        JSON string containing the list of generated files with their paths and content.
    """
    config = GeneratorConfig(
        package_name=package_name,
        schema_type=SchemaType(schema_type),
        use_lombok=use_lombok,
        use_jakarta_validation=use_jakarta_validation,
        use_builder=use_builder,
        serializable=serializable,
        json_include_non_null=json_include_non_null,
    )

    generated = generate_models(schema_content, config)

    result = {
        "total_files": len(generated),
        "files": [
            {
                "file_name": gf.file_name,
                "file_path": gf.file_path,
                "content": gf.content,
            }
            for gf in generated
        ],
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def generate_java_models_from_attachment(
    file_content_base64: str,
    file_name: str,
    schema_type: str = "json",
    package_name: str = "com.example.dto",
    use_lombok: bool = True,
    use_jakarta_validation: bool = True,
    use_builder: bool = True,
    serializable: bool = True,
    json_include_non_null: bool = True,
) -> str:
    """Generate Java models from a base64-encoded schema file or ZIP attachment.

    Use this when the schema is provided as a file attachment. Supports individual
    schema files (.xsd, .json) or ZIP archives containing multiple schemas.

    Args:
        file_content_base64: Base64-encoded content of the schema file or ZIP.
        file_name: Original file name (used to detect format, e.g., "schema.xsd").
        schema_type: Default schema type if not detectable from filename ("xsd" or "json").
        package_name: Java package name for generated classes.
        use_lombok: Add Lombok annotations.
        use_jakarta_validation: Add Jakarta validation annotations.
        use_builder: Add Lombok @Builder annotation.
        serializable: Implement java.io.Serializable.
        json_include_non_null: Add @JsonInclude(NON_NULL).

    Returns:
        JSON string containing the list of generated files with their paths and content.
    """
    raw_bytes = base64.b64decode(file_content_base64)
    all_generated = []

    base_config = {
        "package_name": package_name,
        "use_lombok": use_lombok,
        "use_jakarta_validation": use_jakarta_validation,
        "use_builder": use_builder,
        "serializable": serializable,
        "json_include_non_null": json_include_non_null,
    }

    if file_name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith((".xsd", ".json")):
                    content = zf.read(name).decode("utf-8")
                    detected_type = SchemaType.XSD if name.endswith(".xsd") else SchemaType.JSON_SCHEMA
                    config = GeneratorConfig(schema_type=detected_type, **base_config)
                    all_generated.extend(generate_models(content, config))
    else:
        content = raw_bytes.decode("utf-8")
        detected_type = SchemaType.XSD if file_name.endswith(".xsd") else SchemaType(schema_type)
        config = GeneratorConfig(schema_type=detected_type, **base_config)
        all_generated = generate_models(content, config)

    result = {
        "total_files": len(all_generated),
        "files": [
            {
                "file_name": gf.file_name,
                "file_path": gf.file_path,
                "content": gf.content,
            }
            for gf in all_generated
        ],
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def generate_java_models_as_zip(
    schema_content: str,
    schema_type: str = "json",
    package_name: str = "com.example.dto",
    use_lombok: bool = True,
    use_jakarta_validation: bool = True,
    use_builder: bool = True,
    serializable: bool = True,
    json_include_non_null: bool = True,
) -> str:
    """Generate Java models and return as a base64-encoded ZIP archive for download.

    Same as generate_java_models but returns a downloadable ZIP archive
    (base64-encoded) instead of individual file contents.

    Args:
        schema_content: The raw schema content (XSD XML or JSON Schema string).
        schema_type: Schema format - "xsd" or "json".
        package_name: Java package name for generated classes.
        use_lombok: Add Lombok annotations.
        use_jakarta_validation: Add Jakarta validation annotations.
        use_builder: Add Lombok @Builder annotation.
        serializable: Implement java.io.Serializable.
        json_include_non_null: Add @JsonInclude(NON_NULL).

    Returns:
        JSON with base64-encoded ZIP content and metadata.
    """
    config = GeneratorConfig(
        package_name=package_name,
        schema_type=SchemaType(schema_type),
        use_lombok=use_lombok,
        use_jakarta_validation=use_jakarta_validation,
        use_builder=use_builder,
        serializable=serializable,
        json_include_non_null=json_include_non_null,
    )

    zip_bytes = generate_to_zip(schema_content, config)
    generated = generate_models(schema_content, config)

    result = {
        "total_files": len(generated),
        "file_names": [gf.file_name for gf in generated],
        "zip_base64": base64.b64encode(zip_bytes).decode("ascii"),
        "zip_filename": "generated-models.zip",
    }

    return json.dumps(result)


@mcp.tool()
def list_supported_schema_types() -> str:
    """List all supported schema types for Java model generation.

    Returns:
        JSON string with the list of supported schema types.
    """
    return json.dumps({
        "schema_types": [
            {"value": "json", "label": "JSON Schema", "extensions": [".json"]},
            {"value": "xsd", "label": "XML Schema (XSD)", "extensions": [".xsd"]},
        ]
    })


def main():
    """Run the MCP server standalone (stdio transport)."""
    mcp.run()


def main_http(host: str = "0.0.0.0", port: int = 8101):
    """Run the MCP server standalone as Streamable HTTP at /mcp."""
    import uvicorn

    mcp_app = mcp.streamable_http_app()
    uvicorn.run(mcp_app, host=host, port=port)


if __name__ == "__main__":
    main()
