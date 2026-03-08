"""Utility functions for Java code generation."""

from __future__ import annotations

import keyword
import re

# Java reserved keywords
JAVA_RESERVED_KEYWORDS = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "default", "do", "double", "else", "enum",
    "extends", "final", "finally", "float", "for", "goto", "if", "implements",
    "import", "instanceof", "int", "interface", "long", "native", "new",
    "package", "private", "protected", "public", "return", "short", "static",
    "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
    "transient", "try", "void", "volatile", "while", "var", "yield", "record",
    "sealed", "permits", "non-sealed",
}

# XSD built-in type to Java type mapping
XSD_TYPE_MAP = {
    "string": "String",
    "boolean": "Boolean",
    "int": "Integer",
    "integer": "java.math.BigInteger",
    "long": "Long",
    "short": "Short",
    "byte": "Byte",
    "float": "Float",
    "double": "Double",
    "decimal": "java.math.BigDecimal",
    "date": "java.time.LocalDate",
    "dateTime": "java.time.LocalDateTime",
    "time": "java.time.LocalTime",
    "duration": "java.time.Duration",
    "base64Binary": "byte[]",
    "hexBinary": "byte[]",
    "anyURI": "String",
    "QName": "String",
    "NOTATION": "String",
    "normalizedString": "String",
    "token": "String",
    "language": "String",
    "Name": "String",
    "NCName": "String",
    "ID": "String",
    "IDREF": "String",
    "IDREFS": "String",
    "ENTITY": "String",
    "ENTITIES": "String",
    "NMTOKEN": "String",
    "NMTOKENS": "String",
    "nonPositiveInteger": "java.math.BigInteger",
    "negativeInteger": "java.math.BigInteger",
    "nonNegativeInteger": "java.math.BigInteger",
    "positiveInteger": "java.math.BigInteger",
    "unsignedLong": "java.math.BigInteger",
    "unsignedInt": "Long",
    "unsignedShort": "Integer",
    "unsignedByte": "Short",
    "gYear": "String",
    "gYearMonth": "String",
    "gMonth": "String",
    "gMonthDay": "String",
    "gDay": "String",
    "anyType": "Object",
    "anySimpleType": "String",
}

# JSON Schema type to Java type mapping
JSON_TYPE_MAP = {
    "string": "String",
    "integer": "Long",
    "number": "java.math.BigDecimal",
    "boolean": "Boolean",
    "object": "Object",
    "array": "java.util.List",
}

# JSON Schema format to Java type mapping
JSON_FORMAT_MAP = {
    "date": "java.time.LocalDate",
    "date-time": "java.time.LocalDateTime",
    "time": "java.time.LocalTime",
    "email": "String",
    "uri": "String",
    "uuid": "java.util.UUID",
    "int32": "Integer",
    "int64": "Long",
    "float": "Float",
    "double": "Double",
    "byte": "byte[]",
    "binary": "byte[]",
    "duration": "java.time.Duration",
}


def safe_java_identifier(name: str) -> str:
    """Convert a name to a safe Java identifier, avoiding reserved keywords."""
    # Remove invalid characters
    cleaned = re.sub(r"[^a-zA-Z0-9_$]", "_", name)

    # Ensure doesn't start with a digit
    if cleaned and cleaned[0].isdigit():
        cleaned = "_" + cleaned

    # Avoid Java reserved keywords
    if cleaned.lower() in JAVA_RESERVED_KEYWORDS:
        cleaned = cleaned + "Value"

    # Avoid Python keywords too (for safety in generation)
    if keyword.iskeyword(cleaned):
        cleaned = cleaned + "Field"

    return cleaned


def to_camel_case(name: str) -> str:
    """Convert a name to camelCase (for field names)."""
    # Handle already camelCase or single word
    if "_" not in name and "-" not in name and "." not in name:
        if name:
            return name[0].lower() + name[1:]
        return name

    # Split on common separators
    parts = re.split(r"[-_.\s]+", name)
    parts = [p for p in parts if p]

    if not parts:
        return name

    result = parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
    return safe_java_identifier(result)


def to_pascal_case(name: str) -> str:
    """Convert a name to PascalCase (for class names)."""
    # Split on common separators
    parts = re.split(r"[-_.\s]+", name)
    parts = [p for p in parts if p]

    if not parts:
        return name

    result = "".join(p[0].upper() + p[1:] if p else "" for p in parts)
    return safe_java_identifier(result)


def to_upper_snake_case(name: str) -> str:
    """Convert a name to UPPER_SNAKE_CASE (for enum constants)."""
    # Insert underscore before uppercase letters that follow lowercase
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    # Replace non-alphanumeric with underscore
    s = re.sub(r"[^a-zA-Z0-9]", "_", s)
    # Collapse multiple underscores
    s = re.sub(r"_+", "_", s).strip("_")
    result = s.upper()

    if not result or result[0].isdigit():
        result = "VALUE_" + result

    if result.lower() in JAVA_RESERVED_KEYWORDS:
        result = result + "_VALUE"

    return result


def package_to_path(package_name: str) -> str:
    """Convert a Java package name to a directory path."""
    return package_name.replace(".", "/")


def extract_local_name(qname: str) -> str:
    """Extract local name from a potentially namespace-qualified name."""
    if "}" in qname:
        return qname.split("}")[-1]
    if ":" in qname:
        return qname.split(":")[-1]
    return qname


def simple_type_name(java_type: str) -> str:
    """Get the simple class name from a fully qualified Java type."""
    if "." in java_type:
        return java_type.rsplit(".", 1)[-1]
    return java_type
