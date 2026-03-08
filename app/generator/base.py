"""Base orchestrator for Java model generation."""

from __future__ import annotations

import io
import os
import zipfile

from .java_emitter import emit_class, emit_enum
from .json_parser import parse_json_schema
from .models import GeneratedFile, GeneratorConfig, SchemaType
from .xsd_parser import parse_xsd


def generate_models(
    schema_content: str,
    config: GeneratorConfig,
) -> list[GeneratedFile]:
    """Generate Java model files from a schema.

    Args:
        schema_content: The raw schema content (XSD or JSON Schema).
        config: Generator configuration.

    Returns:
        List of generated Java files.
    """
    if config.schema_type == SchemaType.XSD:
        classes, enums = parse_xsd(schema_content, config)
    elif config.schema_type == SchemaType.JSON_SCHEMA:
        classes, enums = parse_json_schema(schema_content, config)
    else:
        raise ValueError(f"Unsupported schema type: {config.schema_type}")

    generated_files: list[GeneratedFile] = []

    # Emit enum files (top-level enums only; inner enums are emitted inside their class)
    for java_enum in enums:
        gf = emit_enum(java_enum, config)
        generated_files.append(gf)

    # Emit class files
    for java_class in classes:
        gf = emit_class(java_class, config)
        generated_files.append(gf)

    return generated_files


def generate_to_directory(
    schema_content: str,
    config: GeneratorConfig,
) -> list[str]:
    """Generate Java model files and write them to the target directory.

    Returns:
        List of absolute file paths written.
    """
    if not config.target_path:
        raise ValueError("target_path must be set in config")

    files = generate_models(schema_content, config)
    written_paths: list[str] = []

    for gf in files:
        full_path = os.path.join(config.target_path, gf.file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(gf.content)
        written_paths.append(full_path)

    return written_paths


def generate_to_zip(
    schema_content: str,
    config: GeneratorConfig,
) -> bytes:
    """Generate Java model files and return them as a ZIP archive.

    Returns:
        ZIP file content as bytes.
    """
    files = generate_models(schema_content, config)
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for gf in files:
            zf.writestr(gf.file_path, gf.content)

    return buf.getvalue()
