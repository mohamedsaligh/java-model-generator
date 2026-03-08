"""Emit Java source code from intermediate model representations."""

from __future__ import annotations

from .models import (
    GeneratedFile,
    GeneratorConfig,
    JavaClass,
    JavaEnum,
    JavaField,
    JavaFieldConstraint,
)
from .utils import package_to_path, simple_type_name


def emit_class(java_class: JavaClass, config: GeneratorConfig) -> GeneratedFile:
    """Generate a Java class file from a JavaClass model."""
    imports = _collect_class_imports(java_class, config)
    lines: list[str] = []

    # Package declaration
    lines.append(f"package {java_class.package_name};")
    lines.append("")

    # Imports
    if imports:
        for imp in sorted(imports):
            lines.append(f"import {imp};")
        lines.append("")

    # Class-level annotations
    if config.use_lombok:
        lines.append("@Data")
        lines.append("@NoArgsConstructor")
        lines.append("@AllArgsConstructor")
        if config.use_builder:
            lines.append("@Builder")
            if java_class.parent_class:
                lines.append("@SuperBuilder")

    if config.json_include_non_null:
        lines.append("@JsonInclude(JsonInclude.Include.NON_NULL)")

    # Class declaration
    class_decl = f"public class {java_class.name}"
    if java_class.parent_class:
        class_decl += f" extends {java_class.parent_class}"
    ifaces = list(java_class.interfaces)
    if config.serializable:
        ifaces.append("Serializable")
    if ifaces:
        class_decl += f" implements {', '.join(ifaces)}"
    class_decl += " {"

    lines.append(class_decl)
    lines.append("")

    # Serial version UID
    if config.serializable:
        lines.append("    private static final long serialVersionUID = 1L;")
        lines.append("")

    # Inner enums
    for inner_enum in java_class.inner_enums:
        enum_lines = _emit_inner_enum(inner_enum)
        lines.extend(f"    {l}" if l.strip() else "" for l in enum_lines)
        lines.append("")

    # Fields
    for field in java_class.fields:
        field_lines = _emit_field(field, config)
        lines.extend(f"    {l}" for l in field_lines)
        lines.append("")

    # Remove trailing empty line before closing brace
    if lines and lines[-1] == "":
        lines.pop()

    lines.append("}")
    lines.append("")

    pkg_path = package_to_path(java_class.package_name)
    file_name = f"{java_class.name}.java"

    return GeneratedFile(
        file_name=file_name,
        file_path=f"{pkg_path}/{file_name}",
        content="\n".join(lines),
    )


def emit_enum(java_enum: JavaEnum, config: GeneratorConfig) -> GeneratedFile:
    """Generate a Java enum file from a JavaEnum model."""
    imports = set()
    imports.add("com.fasterxml.jackson.annotation.JsonValue")
    imports.add("com.fasterxml.jackson.annotation.JsonCreator")
    if config.use_lombok:
        imports.add("lombok.Getter")

    lines: list[str] = []

    # Package
    lines.append(f"package {java_enum.package_name};")
    lines.append("")

    # Imports
    for imp in sorted(imports):
        lines.append(f"import {imp};")
    lines.append("")

    # Annotations
    if config.use_lombok:
        lines.append("@Getter")

    # Enum declaration
    lines.append(f"public enum {java_enum.name} {{")
    lines.append("")

    # Values
    for i, val in enumerate(java_enum.values):
        separator = "," if i < len(java_enum.values) - 1 else ";"
        lines.append(f'    {val.name}("{val.value}"){separator}')

    lines.append("")

    # Value field and constructor (always explicit for enums)
    lines.append("    private final String value;")
    lines.append("")
    lines.append(f"    {java_enum.name}(String value) {{")
    lines.append("        this.value = value;")
    lines.append("    }")
    lines.append("")

    if not config.use_lombok:
        lines.append("    public String getValue() {")
        lines.append("        return value;")
        lines.append("    }")
        lines.append("")

    lines.append("    @JsonValue")
    lines.append("    public String toValue() {")
    lines.append("        return value;")
    lines.append("    }")
    lines.append("")

    lines.append("    @JsonCreator")
    lines.append(f"    public static {java_enum.name} fromValue(String value) {{")
    lines.append(f"        for ({java_enum.name} item : {java_enum.name}.values()) {{")
    lines.append("            if (item.value.equals(value)) {")
    lines.append("                return item;")
    lines.append("            }")
    lines.append("        }")
    lines.append(
        f'        throw new IllegalArgumentException("Unknown value: " + value);'
    )
    lines.append("    }")
    lines.append("}")
    lines.append("")

    pkg_path = package_to_path(java_enum.package_name)
    file_name = f"{java_enum.name}.java"

    return GeneratedFile(
        file_name=file_name,
        file_path=f"{pkg_path}/{file_name}",
        content="\n".join(lines),
    )


def _emit_field(field: JavaField, config: GeneratorConfig) -> list[str]:
    """Emit field declaration with annotations."""
    lines: list[str] = []

    # Jackson annotation for property name mapping
    if field.json_property_name:
        lines.append(f'@JsonProperty("{field.json_property_name}")')

    # Validation annotations
    if config.use_jakarta_validation:
        constraint_annotations = _emit_constraints(field.constraints, field.java_type)
        lines.extend(constraint_annotations)

    # Determine the actual Java type for declaration
    if field.is_list:
        item_type = field.list_item_type or "Object"
        declared_type = f"List<{simple_type_name(item_type)}>"
    else:
        declared_type = simple_type_name(field.java_type)

    # Field declaration
    lines.append(f"private {declared_type} {field.name};")

    return lines


def _emit_constraints(constraints: JavaFieldConstraint, java_type: str) -> list[str]:
    """Emit Jakarta validation annotations for constraints."""
    annotations: list[str] = []

    if constraints.not_null:
        annotations.append("@NotNull")

    if constraints.not_blank:
        annotations.append("@NotBlank")

    if constraints.not_empty:
        annotations.append("@NotEmpty")

    if constraints.email:
        annotations.append("@Email")

    if constraints.valid:
        annotations.append("@Valid")

    # Size annotation (for strings and collections)
    if constraints.min_length is not None or constraints.max_length is not None:
        parts = []
        if constraints.min_length is not None:
            parts.append(f"min = {constraints.min_length}")
        if constraints.max_length is not None:
            parts.append(f"max = {constraints.max_length}")
        annotations.append(f"@Size({', '.join(parts)})")

    # Collection size
    if constraints.size_min is not None or constraints.size_max is not None:
        parts = []
        if constraints.size_min is not None:
            parts.append(f"min = {constraints.size_min}")
        if constraints.size_max is not None:
            parts.append(f"max = {constraints.size_max}")
        annotations.append(f"@Size({', '.join(parts)})")

    # Min/Max for numeric types
    if constraints.min_value is not None:
        if constraints.min_exclusive:
            annotations.append(
                f'@DecimalMin(value = "{constraints.min_value}", inclusive = false)'
            )
        else:
            annotations.append(f'@DecimalMin(value = "{constraints.min_value}")')

    if constraints.max_value is not None:
        if constraints.max_exclusive:
            annotations.append(
                f'@DecimalMax(value = "{constraints.max_value}", inclusive = false)'
            )
        else:
            annotations.append(f'@DecimalMax(value = "{constraints.max_value}")')

    # Pattern
    if constraints.pattern:
        escaped = constraints.pattern.replace("\\", "\\\\").replace('"', '\\"')
        annotations.append(f'@Pattern(regexp = "{escaped}")')

    # Digits
    if constraints.digits_integer is not None or constraints.digits_fraction is not None:
        integer_part = constraints.digits_integer or 0
        fraction_part = constraints.digits_fraction or 0
        annotations.append(
            f"@Digits(integer = {integer_part}, fraction = {fraction_part})"
        )

    # Positive/Negative
    if constraints.positive:
        annotations.append("@Positive")
    if constraints.positive_or_zero:
        annotations.append("@PositiveOrZero")
    if constraints.negative:
        annotations.append("@Negative")
    if constraints.negative_or_zero:
        annotations.append("@NegativeOrZero")

    # Temporal
    if constraints.future:
        annotations.append("@Future")
    if constraints.past:
        annotations.append("@Past")

    return annotations


def _emit_inner_enum(java_enum: JavaEnum) -> list[str]:
    """Emit an inner enum definition."""
    lines: list[str] = []
    lines.append(f"public enum {java_enum.name} {{")

    for i, val in enumerate(java_enum.values):
        separator = "," if i < len(java_enum.values) - 1 else ";"
        lines.append(f'    {val.name}("{val.value}"){separator}')

    lines.append("")
    lines.append("    private final String value;")
    lines.append("")
    lines.append(f"    {java_enum.name}(String value) {{")
    lines.append("        this.value = value;")
    lines.append("    }")
    lines.append("")
    lines.append("    @com.fasterxml.jackson.annotation.JsonValue")
    lines.append("    public String toValue() {")
    lines.append("        return value;")
    lines.append("    }")
    lines.append("")
    lines.append(f"    @com.fasterxml.jackson.annotation.JsonCreator")
    lines.append(f"    public static {java_enum.name} fromValue(String value) {{")
    lines.append(f"        for ({java_enum.name} item : {java_enum.name}.values()) {{")
    lines.append("            if (item.value.equals(value)) {")
    lines.append("                return item;")
    lines.append("            }")
    lines.append("        }")
    lines.append(
        f'        throw new IllegalArgumentException("Unknown value: " + value);'
    )
    lines.append("    }")
    lines.append("}")

    return lines


def _collect_class_imports(java_class: JavaClass, config: GeneratorConfig) -> set[str]:
    """Collect all needed Java imports for a class."""
    imports: set[str] = set()

    # Lombok
    if config.use_lombok:
        imports.add("lombok.Data")
        imports.add("lombok.NoArgsConstructor")
        imports.add("lombok.AllArgsConstructor")
        if config.use_builder:
            imports.add("lombok.Builder")
            if java_class.parent_class:
                imports.add("lombok.experimental.SuperBuilder")

    # Serializable
    if config.serializable:
        imports.add("java.io.Serializable")

    # Jackson
    if config.json_include_non_null:
        imports.add("com.fasterxml.jackson.annotation.JsonInclude")

    has_json_property = False

    for field in java_class.fields:
        if field.json_property_name:
            has_json_property = True

        # Type imports
        _add_type_import(field.java_type, imports)
        if field.is_list:
            imports.add("java.util.List")
            if field.list_item_type:
                _add_type_import(field.list_item_type, imports)

        if "Map<" in field.java_type:
            imports.add("java.util.Map")

        # Validation imports
        if config.use_jakarta_validation:
            _add_constraint_imports(field.constraints, imports)

    if has_json_property:
        imports.add("com.fasterxml.jackson.annotation.JsonProperty")

    return imports


def _add_type_import(java_type: str, imports: set[str]):
    """Add import for a Java type if needed."""
    # Strip generics before checking for import
    base_type = java_type.split("<")[0].strip() if "<" in java_type else java_type

    # Types that need explicit import (have a package prefix)
    if base_type.startswith("java.") or base_type.startswith("javax."):
        imports.add(base_type)

    # Handle generic type parameters like Map<String, X> or List<Foo>
    if "<" in java_type:
        inner = java_type[java_type.index("<") + 1 : java_type.rindex(">")]
        for part in inner.split(","):
            part = part.strip()
            _add_type_import(part, imports)


def _add_constraint_imports(constraints: JavaFieldConstraint, imports: set[str]):
    """Add Jakarta validation imports based on constraints."""
    base = "jakarta.validation.constraints"

    if constraints.not_null:
        imports.add(f"{base}.NotNull")
    if constraints.not_blank:
        imports.add(f"{base}.NotBlank")
    if constraints.not_empty:
        imports.add(f"{base}.NotEmpty")
    if constraints.email:
        imports.add(f"{base}.Email")
    if constraints.valid:
        imports.add("jakarta.validation.Valid")
    if constraints.min_length is not None or constraints.max_length is not None:
        imports.add(f"{base}.Size")
    if constraints.size_min is not None or constraints.size_max is not None:
        imports.add(f"{base}.Size")
    if constraints.min_value is not None:
        imports.add(f"{base}.DecimalMin")
    if constraints.max_value is not None:
        imports.add(f"{base}.DecimalMax")
    if constraints.pattern:
        imports.add(f"{base}.Pattern")
    if constraints.digits_integer is not None or constraints.digits_fraction is not None:
        imports.add(f"{base}.Digits")
    if constraints.positive:
        imports.add(f"{base}.Positive")
    if constraints.positive_or_zero:
        imports.add(f"{base}.PositiveOrZero")
    if constraints.negative:
        imports.add(f"{base}.Negative")
    if constraints.negative_or_zero:
        imports.add(f"{base}.NegativeOrZero")
    if constraints.future:
        imports.add(f"{base}.Future")
    if constraints.past:
        imports.add(f"{base}.Past")
