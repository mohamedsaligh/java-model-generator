"""Parse XSD schema files into intermediate Java model representations."""

from __future__ import annotations

from lxml import etree

from .models import (
    JavaClass,
    JavaEnum,
    JavaEnumValue,
    JavaField,
    JavaFieldConstraint,
    GeneratorConfig,
)
from .utils import (
    XSD_TYPE_MAP,
    extract_local_name,
    to_camel_case,
    to_pascal_case,
    to_upper_snake_case,
)

XSD_NS = "http://www.w3.org/2001/XMLSchema"
NS = {"xs": XSD_NS}


def parse_xsd(xsd_content: str, config: GeneratorConfig) -> tuple[list[JavaClass], list[JavaEnum]]:
    """Parse XSD content and return Java classes and enums."""
    root = etree.fromstring(xsd_content.encode("utf-8") if isinstance(xsd_content, str) else xsd_content)
    target_ns = root.get("targetNamespace", "")

    classes: list[JavaClass] = []
    enums: list[JavaEnum] = []

    # Track named simple types (for enums and type aliases)
    simple_type_map: dict[str, str] = {}  # name -> java type or enum name
    enum_names: set[str] = set()

    # First pass: collect all named simpleTypes (enums and restrictions)
    for st in root.findall("xs:simpleType", NS):
        name = st.get("name")
        if not name:
            continue
        restriction = st.find("xs:restriction", NS)
        if restriction is not None:
            enum_values = restriction.findall("xs:enumeration", NS)
            if enum_values:
                enum_name = to_pascal_case(name)
                enum_names.add(enum_name)
                simple_type_map[name] = enum_name
                enum = _parse_enum(name, enum_values, config)
                enums.append(enum)
            else:
                base = extract_local_name(restriction.get("base", "string"))
                simple_type_map[name] = XSD_TYPE_MAP.get(base, "String")

    # Second pass: collect all named complexTypes
    for ct in root.findall("xs:complexType", NS):
        name = ct.get("name")
        if not name:
            continue
        java_class = _parse_complex_type(ct, name, config, simple_type_map, enum_names, target_ns)
        classes.append(java_class)

    # Third pass: top-level elements that define inline types
    for elem in root.findall("xs:element", NS):
        elem_name = elem.get("name")
        if not elem_name:
            continue

        # Check if it references a named type
        elem_type = elem.get("type")
        if elem_type:
            local_type = extract_local_name(elem_type)
            # If it references an already-parsed complexType, skip
            if any(c.name == to_pascal_case(local_type) for c in classes):
                continue

        # Check for inline complexType
        ct = elem.find("xs:complexType", NS)
        if ct is not None:
            java_class = _parse_complex_type(ct, elem_name, config, simple_type_map, enum_names, target_ns)
            classes.append(java_class)

        # Check for inline simpleType with enum
        st = elem.find("xs:simpleType", NS)
        if st is not None:
            restriction = st.find("xs:restriction", NS)
            if restriction is not None:
                enum_values = restriction.findall("xs:enumeration", NS)
                if enum_values:
                    enum_name = to_pascal_case(elem_name)
                    if enum_name not in enum_names:
                        enum = _parse_enum(elem_name, enum_values, config)
                        enums.append(enum)
                        enum_names.add(enum_name)

    return classes, enums


def _parse_enum(
    name: str,
    enum_elements: list,
    config: GeneratorConfig,
) -> JavaEnum:
    """Parse XSD enumeration values into a JavaEnum."""
    enum_name = to_pascal_case(name)
    values = []
    for ev in enum_elements:
        raw_value = ev.get("value", "")
        constant_name = to_upper_snake_case(raw_value)
        values.append(JavaEnumValue(name=constant_name, value=raw_value))

    return JavaEnum(
        name=enum_name,
        package_name=config.package_name,
        values=values,
    )


def _parse_complex_type(
    ct_element,
    name: str,
    config: GeneratorConfig,
    simple_type_map: dict[str, str],
    enum_names: set[str],
    target_ns: str,
) -> JavaClass:
    """Parse an XSD complexType into a JavaClass."""
    class_name = to_pascal_case(name)
    fields: list[JavaField] = []
    inner_enums: list[JavaEnum] = []
    parent_class = None

    # Handle complexContent (extension/restriction)
    complex_content = ct_element.find("xs:complexContent", NS)
    if complex_content is not None:
        extension = complex_content.find("xs:extension", NS)
        if extension is not None:
            base = extract_local_name(extension.get("base", ""))
            parent_class = to_pascal_case(base)
            # Parse fields from extension
            _collect_fields(extension, fields, inner_enums, config, simple_type_map, enum_names, class_name)
        restriction = complex_content.find("xs:restriction", NS)
        if restriction is not None:
            base = extract_local_name(restriction.get("base", ""))
            parent_class = to_pascal_case(base)
            _collect_fields(restriction, fields, inner_enums, config, simple_type_map, enum_names, class_name)
    else:
        # Direct sequence/all/choice
        _collect_fields(ct_element, fields, inner_enums, config, simple_type_map, enum_names, class_name)

    # Handle attributes
    for attr in ct_element.findall(".//xs:attribute", NS):
        field = _parse_attribute(attr, config, simple_type_map, enum_names, class_name, inner_enums)
        if field:
            fields.append(field)

    return JavaClass(
        name=class_name,
        package_name=config.package_name,
        fields=fields,
        parent_class=parent_class,
        inner_enums=inner_enums,
    )


def _collect_fields(
    parent_element,
    fields: list[JavaField],
    inner_enums: list[JavaEnum],
    config: GeneratorConfig,
    simple_type_map: dict[str, str],
    enum_names: set[str],
    owner_class: str,
):
    """Collect fields from sequence, all, or choice elements."""
    for container_tag in ["xs:sequence", "xs:all", "xs:choice"]:
        container = parent_element.find(container_tag, NS)
        if container is not None:
            is_choice = container_tag == "xs:choice"
            for elem in container.findall("xs:element", NS):
                field = _parse_element_field(
                    elem, config, simple_type_map, enum_names, owner_class, inner_enums, is_choice
                )
                if field:
                    fields.append(field)

            # Nested groups
            for group_ref in container.findall("xs:group", NS):
                ref = group_ref.get("ref")
                if ref:
                    # Group references would need global resolution; treat as Object
                    pass

    # Also handle direct elements (no container)
    for elem in parent_element.findall("xs:element", NS):
        field = _parse_element_field(
            elem, config, simple_type_map, enum_names, owner_class, inner_enums, False
        )
        if field and not any(f.name == field.name for f in fields):
            fields.append(field)


def _parse_element_field(
    elem,
    config: GeneratorConfig,
    simple_type_map: dict[str, str],
    enum_names: set[str],
    owner_class: str,
    inner_enums: list[JavaEnum],
    is_choice: bool,
) -> JavaField | None:
    """Parse an xs:element into a JavaField."""
    elem_name = elem.get("name")
    if not elem_name:
        # Could be a ref
        ref = elem.get("ref")
        if ref:
            elem_name = extract_local_name(ref)
        else:
            return None

    field_name = to_camel_case(elem_name)
    min_occurs = elem.get("minOccurs", "1")
    max_occurs = elem.get("maxOccurs", "1")
    is_list = max_occurs == "unbounded" or (max_occurs.isdigit() and int(max_occurs) > 1)
    is_required = not is_choice and min_occurs != "0"

    # Determine Java type
    java_type = "String"
    is_enum = False
    json_property_name = elem_name if elem_name != field_name else None

    elem_type = elem.get("type")
    if elem_type:
        local_type = extract_local_name(elem_type)
        if local_type in simple_type_map:
            java_type = simple_type_map[local_type]
            is_enum = java_type in enum_names
        elif local_type in XSD_TYPE_MAP:
            java_type = XSD_TYPE_MAP[local_type]
        else:
            # Assume it's a reference to a complexType
            java_type = to_pascal_case(local_type)
    else:
        # Check for inline simpleType
        inline_st = elem.find("xs:simpleType", NS)
        if inline_st is not None:
            restriction = inline_st.find("xs:restriction", NS)
            if restriction is not None:
                enum_values = restriction.findall("xs:enumeration", NS)
                if enum_values:
                    enum_name = to_pascal_case(elem_name)
                    inner_enum = _parse_enum(elem_name, enum_values, config)
                    inner_enum.name = enum_name
                    inner_enums.append(inner_enum)
                    java_type = enum_name
                    is_enum = True
                else:
                    base = extract_local_name(restriction.get("base", "string"))
                    java_type = XSD_TYPE_MAP.get(base, "String")

        # Check for inline complexType
        inline_ct = elem.find("xs:complexType", NS)
        if inline_ct is not None:
            java_type = to_pascal_case(elem_name)

    constraints = _extract_constraints(elem, java_type, is_required)

    return JavaField(
        name=field_name,
        java_type=java_type,
        required=is_required,
        constraints=constraints,
        json_property_name=json_property_name,
        is_list=is_list,
        list_item_type=java_type if is_list else None,
        is_enum_type=is_enum,
    )


def _parse_attribute(
    attr,
    config: GeneratorConfig,
    simple_type_map: dict[str, str],
    enum_names: set[str],
    owner_class: str,
    inner_enums: list[JavaEnum],
) -> JavaField | None:
    """Parse an xs:attribute into a JavaField."""
    attr_name = attr.get("name")
    if not attr_name:
        return None

    field_name = to_camel_case(attr_name)
    is_required = attr.get("use") == "required"
    json_property_name = attr_name if attr_name != field_name else None

    java_type = "String"
    is_enum = False

    attr_type = attr.get("type")
    if attr_type:
        local_type = extract_local_name(attr_type)
        if local_type in simple_type_map:
            java_type = simple_type_map[local_type]
            is_enum = java_type in enum_names
        elif local_type in XSD_TYPE_MAP:
            java_type = XSD_TYPE_MAP[local_type]
        else:
            java_type = to_pascal_case(local_type)
    else:
        inline_st = attr.find("xs:simpleType", NS)
        if inline_st is not None:
            restriction = inline_st.find("xs:restriction", NS)
            if restriction is not None:
                enum_values = restriction.findall("xs:enumeration", NS)
                if enum_values:
                    enum_name = to_pascal_case(attr_name)
                    inner_enum = _parse_enum(attr_name, enum_values, config)
                    inner_enum.name = enum_name
                    inner_enums.append(inner_enum)
                    java_type = enum_name
                    is_enum = True
                else:
                    base = extract_local_name(restriction.get("base", "string"))
                    java_type = XSD_TYPE_MAP.get(base, "String")

    constraints = JavaFieldConstraint(not_null=is_required)

    return JavaField(
        name=field_name,
        java_type=java_type,
        required=is_required,
        constraints=constraints,
        json_property_name=json_property_name,
        is_enum_type=is_enum,
    )


def _extract_constraints(elem, java_type: str, is_required: bool) -> JavaFieldConstraint:
    """Extract validation constraints from an XSD element."""
    constraints = JavaFieldConstraint(not_null=is_required)

    # Look for simpleType restrictions within
    restriction = elem.find(".//xs:restriction", NS)
    if restriction is not None:
        for facet in restriction:
            tag = etree.QName(facet.tag).localname
            value = facet.get("value", "")

            if tag == "minLength":
                constraints.min_length = int(value)
            elif tag == "maxLength":
                constraints.max_length = int(value)
            elif tag == "length":
                constraints.min_length = int(value)
                constraints.max_length = int(value)
            elif tag == "pattern":
                constraints.pattern = value
            elif tag == "minInclusive":
                constraints.min_value = value
            elif tag == "maxInclusive":
                constraints.max_value = value
            elif tag == "minExclusive":
                constraints.min_value = value
                constraints.min_exclusive = True
            elif tag == "maxExclusive":
                constraints.max_value = value
                constraints.max_exclusive = True
            elif tag == "totalDigits":
                constraints.digits_integer = int(value)
            elif tag == "fractionDigits":
                constraints.digits_fraction = int(value)

    if is_required and java_type == "String":
        constraints.not_blank = True

    return constraints
