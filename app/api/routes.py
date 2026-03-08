"""FastAPI routes for the Java model generator."""

from __future__ import annotations

import io
import tempfile
import zipfile
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..generator.base import generate_models, generate_to_directory, generate_to_zip
from ..generator.models import GeneratedFile, GeneratorConfig, SchemaType

router = APIRouter(prefix="/api/v1", tags=["Java Model Generator"])


_EXAMPLE_SCHEMA = """{
  "title": "User",
  "type": "object",
  "properties": {
    "id": { "type": "integer", "format": "int64" },
    "username": { "type": "string", "minLength": 3, "maxLength": 50 },
    "email": { "type": "string", "format": "email" },
    "roles": { "type": "array", "items": { "type": "string", "enum": ["ADMIN", "USER", "GUEST"] } }
  },
  "required": ["id", "username", "email"]
}"""


class GenerateRequest(BaseModel):
    """Request body for Java model generation from inline schema content."""

    schema_content: str = Field(
        ...,
        description="The schema content (JSON Schema or XSD) as a string.",
        json_schema_extra={"example": _EXAMPLE_SCHEMA},
    )
    package_name: str = Field(
        default="com.example.dto",
        description="Java package name for generated classes.",
        json_schema_extra={"example": "com.example.dto"},
    )
    schema_type: SchemaType = Field(
        default=SchemaType.JSON_SCHEMA,
        description="Type of the input schema (`json` or `xsd`).",
    )
    target_path: Optional[str] = Field(
        default=None,
        description="If set, write generated `.java` files to this directory on the server.",
    )
    use_lombok: bool = Field(default=True, description="Add Lombok annotations (@Data, @Builder, etc.).")
    use_jakarta_validation: bool = Field(default=True, description="Add Jakarta validation annotations.")
    use_builder: bool = Field(default=True, description="Add Lombok @Builder annotation.")
    serializable: bool = Field(default=True, description="Implement java.io.Serializable.")
    json_include_non_null: bool = Field(default=True, description="Add @JsonInclude(NON_NULL).")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "schema_content": _EXAMPLE_SCHEMA,
                    "package_name": "com.example.dto",
                    "schema_type": "json",
                    "use_lombok": True,
                    "use_jakarta_validation": True,
                    "use_builder": True,
                    "serializable": True,
                    "json_include_non_null": True,
                }
            ]
        }
    }


class GeneratedFileResponse(BaseModel):
    """A single generated Java source file."""

    file_name: str = Field(..., description="Java file name.", json_schema_extra={"example": "User.java"})
    file_path: str = Field(
        ...,
        description="Relative path including package directories.",
        json_schema_extra={"example": "com/example/dto/User.java"},
    )
    content: str = Field(
        ...,
        description="Full Java source code content.",
        json_schema_extra={"example": "package com.example.dto;\n\nimport lombok.*;\n\n@Data\npublic class User {\n    private Long id;\n    private String username;\n}"},
    )


class GenerateResponse(BaseModel):
    """Response containing all generated Java source files."""

    files: list[GeneratedFileResponse] = Field(..., description="List of generated Java source files.")
    total_files: int = Field(..., description="Total number of generated files.", json_schema_extra={"example": 2})


@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Generate Java models from schema content (JSON body)",
    description="Accepts schema content as a JSON payload and returns generated Java source files.",
)
async def generate_from_json(request: GenerateRequest):
    """Generate Java DTO models from schema content provided in JSON body."""
    config = GeneratorConfig(
        package_name=request.package_name,
        schema_type=request.schema_type,
        target_path=request.target_path,
        use_lombok=request.use_lombok,
        use_jakarta_validation=request.use_jakarta_validation,
        use_builder=request.use_builder,
        serializable=request.serializable,
        json_include_non_null=request.json_include_non_null,
    )

    try:
        if request.target_path:
            paths = generate_to_directory(request.schema_content, config)
            files = [
                GeneratedFileResponse(file_name=p.split("/")[-1], file_path=p, content="")
                for p in paths
            ]
            return GenerateResponse(files=files, total_files=len(files))

        generated = generate_models(request.schema_content, config)
        files = [
            GeneratedFileResponse(
                file_name=gf.file_name, file_path=gf.file_path, content=gf.content
            )
            for gf in generated
        ]
        return GenerateResponse(files=files, total_files=len(files))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/generate/upload",
    response_model=GenerateResponse,
    summary="Generate Java models from uploaded schema file",
    description="Upload a schema file (.xsd, .json) or a ZIP containing multiple schema files.",
)
async def generate_from_upload(
    file: UploadFile = File(..., description="Schema file (.xsd, .json) or .zip"),
    package_name: str = Form("com.example.dto"),
    schema_type: SchemaType = Form(SchemaType.JSON_SCHEMA),
    target_path: Optional[str] = Form(None),
    use_lombok: bool = Form(True),
    use_jakarta_validation: bool = Form(True),
    use_builder: bool = Form(True),
    serializable: bool = Form(True),
    json_include_non_null: bool = Form(True),
):
    """Generate Java DTO models from an uploaded schema file or ZIP."""
    config = GeneratorConfig(
        package_name=package_name,
        schema_type=schema_type,
        target_path=target_path,
        use_lombok=use_lombok,
        use_jakarta_validation=use_jakarta_validation,
        use_builder=use_builder,
        serializable=serializable,
        json_include_non_null=json_include_non_null,
    )

    try:
        content_bytes = await file.read()
        all_generated: list[GeneratedFile] = []

        if file.filename and file.filename.endswith(".zip"):
            # Process ZIP: extract and generate from each schema file
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as zf:
                for name in zf.namelist():
                    if name.endswith((".xsd", ".json")):
                        schema_content = zf.read(name).decode("utf-8")
                        # Auto-detect schema type from extension
                        file_config = GeneratorConfig(
                            **{
                                **config.model_dump(),
                                "schema_type": SchemaType.XSD
                                if name.endswith(".xsd")
                                else SchemaType.JSON_SCHEMA,
                            }
                        )
                        generated = generate_models(schema_content, file_config)
                        all_generated.extend(generated)
        else:
            schema_content = content_bytes.decode("utf-8")
            all_generated = generate_models(schema_content, config)

        # Write to target path if specified
        if target_path:
            import os

            for gf in all_generated:
                full_path = os.path.join(target_path, gf.file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(gf.content)

        files = [
            GeneratedFileResponse(
                file_name=gf.file_name, file_path=gf.file_path, content=gf.content
            )
            for gf in all_generated
        ]
        return GenerateResponse(files=files, total_files=len(files))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/generate/download",
    summary="Generate Java models and download as ZIP",
    description="Upload a schema file and download generated Java sources as a ZIP archive.",
    response_class=StreamingResponse,
)
async def generate_and_download(
    file: UploadFile = File(..., description="Schema file (.xsd, .json) or .zip"),
    package_name: str = Form("com.example.dto"),
    schema_type: SchemaType = Form(SchemaType.JSON_SCHEMA),
    use_lombok: bool = Form(True),
    use_jakarta_validation: bool = Form(True),
    use_builder: bool = Form(True),
    serializable: bool = Form(True),
    json_include_non_null: bool = Form(True),
):
    """Generate Java DTO models and return a ZIP file for download."""
    config = GeneratorConfig(
        package_name=package_name,
        schema_type=schema_type,
        use_lombok=use_lombok,
        use_jakarta_validation=use_jakarta_validation,
        use_builder=use_builder,
        serializable=serializable,
        json_include_non_null=json_include_non_null,
    )

    try:
        content_bytes = await file.read()
        all_generated: list[GeneratedFile] = []

        if file.filename and file.filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as zf:
                for name in zf.namelist():
                    if name.endswith((".xsd", ".json")):
                        schema_content = zf.read(name).decode("utf-8")
                        file_config = GeneratorConfig(
                            **{
                                **config.model_dump(),
                                "schema_type": SchemaType.XSD
                                if name.endswith(".xsd")
                                else SchemaType.JSON_SCHEMA,
                            }
                        )
                        generated = generate_models(schema_content, file_config)
                        all_generated.extend(generated)
        else:
            schema_content = content_bytes.decode("utf-8")
            all_generated = generate_models(schema_content, config)

        # Create ZIP
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for gf in all_generated:
                zf.writestr(gf.file_path, gf.content)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=generated-models.zip"},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/schema-types",
    summary="List supported schema types",
)
async def list_schema_types():
    """Return the list of supported schema types."""
    return {"schema_types": [st.value for st in SchemaType]}
