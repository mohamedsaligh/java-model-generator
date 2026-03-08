"""FastAPI routes for the Java model generator."""

from __future__ import annotations

import io
import tempfile
import zipfile
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ..generator.base import generate_models, generate_to_directory, generate_to_zip
from ..generator.models import GeneratedFile, GeneratorConfig, SchemaType

router = APIRouter(prefix="/api/v1", tags=["Java Model Generator"])


class GenerateRequest(BaseModel):
    schema_content: str
    package_name: str = "com.example.dto"
    schema_type: SchemaType = SchemaType.JSON_SCHEMA
    target_path: Optional[str] = None
    use_lombok: bool = True
    use_jakarta_validation: bool = True
    use_builder: bool = True
    serializable: bool = True
    json_include_non_null: bool = True


class GenerateResponse(BaseModel):
    files: list[GeneratedFileResponse]
    total_files: int


class GeneratedFileResponse(BaseModel):
    file_name: str
    file_path: str
    content: str


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
