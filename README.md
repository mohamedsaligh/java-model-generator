# Java Model Generator

Generate Java DTO model classes from XSD, JSON Schema, and other schema formats. Produces 100% compilable Java source with Lombok annotations, Jakarta validation constraints, and Jackson serialization support.

## Structure

```
java-model-generator/
├── app/
│   ├── generator/
│   │   ├── models.py         # Internal models (JavaClass, JavaField, JavaEnum, etc.)
│   │   ├── utils.py          # Type mappings, naming conventions, keyword safety
│   │   ├── xsd_parser.py     # XSD → intermediate model
│   │   ├── json_parser.py    # JSON Schema → intermediate model
│   │   ├── java_emitter.py   # Intermediate model → Java source code
│   │   └── base.py           # Orchestrator (generate_models, generate_to_zip, etc.)
│   ├── api/
│   │   └── routes.py         # FastAPI endpoints
│   ├── main.py               # FastAPI app entry point
│   └── mcp_server.py         # MCP server with 4 tools
├── tests/
│   └── test_generator.py     # 28 tests (all passing)
├── pyproject.toml
└── requirements.txt
```

## Features

- **Schema support**: XSD and JSON Schema
- **Lombok**: `@Data`, `@NoArgsConstructor`, `@AllArgsConstructor`, `@Builder`
- **Jakarta Validation**: `@NotNull`, `@NotBlank`, `@Size`, `@Pattern`, `@DecimalMin/Max`, `@Email`, `@Digits`, `@Valid`, etc.
- **Jackson**: `@JsonProperty` (for name mapping), `@JsonInclude(NON_NULL)`, `@JsonValue`/`@JsonCreator` on enums
- **Safe naming**: camelCase fields, PascalCase classes, UPPER_SNAKE enums, Java keyword avoidance
- **Compilable**: Verified with `javac 25` + Maven (Lombok 1.18, Jakarta 3.1, Jackson 2.17)

## FastAPI Endpoints (port 8100)

| Endpoint | Description |
|---|---|
| `POST /api/v1/generate` | JSON body with schema content → generated files |
| `POST /api/v1/generate/upload` | Upload `.xsd`, `.json`, or `.zip` → generated files |
| `POST /api/v1/generate/download` | Upload schema → download ZIP |
| `GET /api/v1/schema-types` | List supported schema types |
| `POST /mcp` | MCP JSON-RPC endpoint (Streamable HTTP transport) |
| `GET /docs` | Swagger UI |

## MCP Server

The MCP server is exposed as a JSON-RPC endpoint at `/mcp` on the same FastAPI server (Streamable HTTP transport). It can also run standalone via stdio for direct CLI integration.

### MCP Tools

| Tool | Description |
|---|---|
| `generate_java_models` | Schema string → generated file contents |
| `generate_java_models_from_attachment` | Base64 file/ZIP → generated file contents |
| `generate_java_models_as_zip` | Schema string → base64 ZIP download |
| `list_supported_schema_types` | List supported formats |

### MCP JSON-RPC Usage

```bash
# POST to /mcp with JSON-RPC body
curl -X POST http://localhost:8100/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

## Running

```bash
# FastAPI server (includes both REST API and MCP at /mcp)
cd java-model-generator
pip install -e .
uvicorn app.main:app --port 8100

# MCP server standalone (stdio transport, for CLI tools)
python -m app.mcp_server

# Tests
pytest tests/ -v
```

## MCP Configuration

### Streamable HTTP (recommended, connects to FastAPI server)

```json
{
  "mcpServers": {
    "java-model-generator": {
      "type": "streamable-http",
      "url": "http://localhost:8100/mcp"
    }
  }
}
```

### Stdio (standalone, no server required)

```json
{
  "mcpServers": {
    "java-model-generator": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/path/to/java-model-generator"
    }
  }
}
```

## User Inputs

| Parameter | Description | Default |
|---|---|---|
| `package_name` | Java package for generated classes | `com.example.dto` |
| `schema_type` | Input schema format (`xsd` or `json`) | `json` |
| `target_path` | Directory to write generated files | _(none, returns in response)_ |
| `use_lombok` | Add Lombok annotations | `true` |
| `use_jakarta_validation` | Add Jakarta validation annotations | `true` |
| `use_builder` | Add Lombok `@Builder` | `true` |
| `serializable` | Implement `java.io.Serializable` | `true` |
| `json_include_non_null` | Add `@JsonInclude(NON_NULL)` | `true` |
