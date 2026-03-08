"""Internal models for the Java model generator."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SchemaType(str, Enum):
    XSD = "xsd"
    JSON_SCHEMA = "json"


class GeneratorConfig(BaseModel):
    package_name: str = Field(
        default="com.example.dto",
        description="Java package name for generated classes",
    )
    schema_type: SchemaType = Field(description="Type of the input schema")
    target_path: Optional[str] = Field(
        default=None,
        description="Target directory path to write generated Java files",
    )
    use_lombok: bool = Field(default=True, description="Add Lombok annotations")
    use_jakarta_validation: bool = Field(
        default=True, description="Add Jakarta validation annotations"
    )
    use_builder: bool = Field(
        default=True, description="Add Lombok @Builder annotation"
    )
    generate_toString: bool = Field(
        default=False,
        description="Generate toString (false when Lombok @Data is used)",
    )
    serializable: bool = Field(
        default=True, description="Implement java.io.Serializable"
    )
    json_include_non_null: bool = Field(
        default=True,
        description="Add @JsonInclude(JsonInclude.Include.NON_NULL)",
    )


# --- Java type system models ---


class JavaFieldConstraint(BaseModel):
    not_null: bool = False
    not_blank: bool = False
    not_empty: bool = False
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[str] = None  # String to handle BigDecimal
    max_value: Optional[str] = None
    min_exclusive: bool = False
    max_exclusive: bool = False
    pattern: Optional[str] = None
    size_min: Optional[int] = None
    size_max: Optional[int] = None
    email: bool = False
    digits_integer: Optional[int] = None
    digits_fraction: Optional[int] = None
    positive: bool = False
    positive_or_zero: bool = False
    negative: bool = False
    negative_or_zero: bool = False
    future: bool = False
    past: bool = False
    valid: bool = False  # @Valid for nested objects


class JavaField(BaseModel):
    name: str
    java_type: str
    description: Optional[str] = None
    required: bool = False
    default_value: Optional[str] = None
    constraints: JavaFieldConstraint = Field(default_factory=JavaFieldConstraint)
    json_property_name: Optional[str] = None  # original name if different
    is_list: bool = False
    list_item_type: Optional[str] = None
    is_enum_type: bool = False


class JavaEnumValue(BaseModel):
    name: str  # Java constant name (UPPER_SNAKE)
    value: str  # Original value from schema


class JavaEnum(BaseModel):
    name: str
    package_name: str
    values: list[JavaEnumValue]
    description: Optional[str] = None


class JavaClass(BaseModel):
    name: str
    package_name: str
    fields: list[JavaField]
    description: Optional[str] = None
    parent_class: Optional[str] = None
    interfaces: list[str] = Field(default_factory=list)
    inner_enums: list[JavaEnum] = Field(default_factory=list)
    is_abstract: bool = False


class GeneratedFile(BaseModel):
    file_name: str
    file_path: str  # relative path including package dirs
    content: str
