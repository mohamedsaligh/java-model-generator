"""Tests for the Java model generator."""

import json

import pytest

from app.generator.base import generate_models, generate_to_zip
from app.generator.models import GeneratorConfig, SchemaType

# --- Sample Schemas ---

SAMPLE_JSON_SCHEMA = json.dumps({
    "title": "Order",
    "type": "object",
    "required": ["orderId", "customer", "items", "status"],
    "properties": {
        "orderId": {
            "type": "string",
            "minLength": 1,
            "maxLength": 50,
            "pattern": "^ORD-[0-9]+$"
        },
        "customer": {
            "$ref": "#/definitions/Customer"
        },
        "items": {
            "type": "array",
            "minItems": 1,
            "items": {
                "$ref": "#/definitions/OrderItem"
            }
        },
        "status": {
            "$ref": "#/definitions/OrderStatus"
        },
        "totalAmount": {
            "type": "number",
            "minimum": 0
        },
        "notes": {
            "type": "string",
            "maxLength": 500
        },
        "createdAt": {
            "type": "string",
            "format": "date-time"
        },
        "priority": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5
        }
    },
    "definitions": {
        "Customer": {
            "type": "object",
            "required": ["name", "email"],
            "properties": {
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 100
                },
                "email": {
                    "type": "string",
                    "format": "email"
                },
                "phone": {
                    "type": "string",
                    "pattern": "^\\+?[0-9\\-\\s]+$"
                },
                "address": {
                    "$ref": "#/definitions/Address"
                }
            }
        },
        "Address": {
            "type": "object",
            "required": ["street", "city", "country"],
            "properties": {
                "street": {"type": "string", "maxLength": 200},
                "city": {"type": "string", "maxLength": 100},
                "state": {"type": "string", "maxLength": 100},
                "zipCode": {"type": "string", "pattern": "^[0-9]{5}(-[0-9]{4})?$"},
                "country": {"type": "string", "minLength": 2, "maxLength": 2}
            }
        },
        "OrderItem": {
            "type": "object",
            "required": ["productId", "quantity", "unitPrice"],
            "properties": {
                "productId": {"type": "string"},
                "productName": {"type": "string", "maxLength": 200},
                "quantity": {"type": "integer", "minimum": 1},
                "unitPrice": {"type": "number", "minimum": 0}
            }
        },
        "OrderStatus": {
            "type": "string",
            "enum": ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"]
        }
    }
})

SAMPLE_XSD = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="http://example.com/order"
           xmlns:tns="http://example.com/order"
           elementFormDefault="qualified">

    <xs:simpleType name="OrderStatus">
        <xs:restriction base="xs:string">
            <xs:enumeration value="PENDING"/>
            <xs:enumeration value="CONFIRMED"/>
            <xs:enumeration value="SHIPPED"/>
            <xs:enumeration value="DELIVERED"/>
            <xs:enumeration value="CANCELLED"/>
        </xs:restriction>
    </xs:simpleType>

    <xs:simpleType name="CurrencyCode">
        <xs:restriction base="xs:string">
            <xs:length value="3"/>
            <xs:pattern value="[A-Z]{3}"/>
        </xs:restriction>
    </xs:simpleType>

    <xs:complexType name="Address">
        <xs:sequence>
            <xs:element name="street" type="xs:string" minOccurs="1"/>
            <xs:element name="city" type="xs:string" minOccurs="1"/>
            <xs:element name="state" type="xs:string" minOccurs="0"/>
            <xs:element name="zip-code" type="xs:string" minOccurs="1">
                <xs:simpleType>
                    <xs:restriction base="xs:string">
                        <xs:pattern value="[0-9]{5}(-[0-9]{4})?"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:element>
            <xs:element name="country" type="xs:string" minOccurs="1"/>
        </xs:sequence>
    </xs:complexType>

    <xs:complexType name="Customer">
        <xs:sequence>
            <xs:element name="customer-id" type="xs:string" minOccurs="1"/>
            <xs:element name="first-name" type="xs:string" minOccurs="1">
                <xs:simpleType>
                    <xs:restriction base="xs:string">
                        <xs:minLength value="1"/>
                        <xs:maxLength value="50"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:element>
            <xs:element name="last-name" type="xs:string" minOccurs="1"/>
            <xs:element name="email" type="xs:string" minOccurs="1"/>
            <xs:element name="billing-address" type="tns:Address" minOccurs="0"/>
            <xs:element name="shipping-address" type="tns:Address" minOccurs="0"/>
        </xs:sequence>
        <xs:attribute name="type" type="xs:string" use="required"/>
    </xs:complexType>

    <xs:complexType name="OrderItem">
        <xs:sequence>
            <xs:element name="product-id" type="xs:string" minOccurs="1"/>
            <xs:element name="product-name" type="xs:string" minOccurs="1"/>
            <xs:element name="quantity" type="xs:int" minOccurs="1">
                <xs:simpleType>
                    <xs:restriction base="xs:int">
                        <xs:minInclusive value="1"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:element>
            <xs:element name="unit-price" type="xs:decimal" minOccurs="1"/>
            <xs:element name="currency" type="tns:CurrencyCode" minOccurs="1"/>
        </xs:sequence>
    </xs:complexType>

    <xs:complexType name="Order">
        <xs:sequence>
            <xs:element name="order-id" type="xs:string" minOccurs="1"/>
            <xs:element name="customer" type="tns:Customer" minOccurs="1"/>
            <xs:element name="items" type="tns:OrderItem" minOccurs="1" maxOccurs="unbounded"/>
            <xs:element name="status" type="tns:OrderStatus" minOccurs="1"/>
            <xs:element name="total-amount" type="xs:decimal" minOccurs="1"/>
            <xs:element name="order-date" type="xs:dateTime" minOccurs="1"/>
            <xs:element name="notes" type="xs:string" minOccurs="0"/>
        </xs:sequence>
    </xs:complexType>

    <xs:element name="Order" type="tns:Order"/>
</xs:schema>
"""


class TestJsonSchemaGeneration:
    def _config(self, **kwargs):
        return GeneratorConfig(
            package_name="com.example.order",
            schema_type=SchemaType.JSON_SCHEMA,
            **kwargs,
        )

    def test_generates_all_classes(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        names = {f.file_name for f in files}
        assert "Order.java" in names
        assert "Customer.java" in names
        assert "Address.java" in names
        assert "OrderItem.java" in names
        assert "OrderStatus.java" in names

    def test_package_declaration(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "package com.example.order;" in order.content

    def test_lombok_annotations(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "@Data" in order.content
        assert "@NoArgsConstructor" in order.content
        assert "@AllArgsConstructor" in order.content
        assert "@Builder" in order.content

    def test_jakarta_validation(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "@NotNull" in order.content
        assert "@NotBlank" in order.content

    def test_size_constraint(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "@Size(" in order.content

    def test_pattern_constraint(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "@Pattern(" in order.content

    def test_enum_generation(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        status = next(f for f in files if f.file_name == "OrderStatus.java")
        assert "public enum OrderStatus" in status.content
        assert "PENDING" in status.content
        assert "CANCELLED" in status.content
        assert "@JsonValue" in status.content
        assert "@JsonCreator" in status.content

    def test_serializable(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "implements Serializable" in order.content
        assert "serialVersionUID" in order.content

    def test_json_include(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "@JsonInclude(JsonInclude.Include.NON_NULL)" in order.content

    def test_no_lombok(self):
        files = generate_models(
            SAMPLE_JSON_SCHEMA, self._config(use_lombok=False)
        )
        order = next(f for f in files if f.file_name == "Order.java")
        assert "@Data" not in order.content

    def test_list_field(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "List<OrderItem>" in order.content

    def test_zip_generation(self):
        config = self._config()
        zip_bytes = generate_to_zip(SAMPLE_JSON_SCHEMA, config)
        assert len(zip_bytes) > 0
        import zipfile, io
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert any("Order.java" in n for n in names)

    def test_date_time_type(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "LocalDateTime" in order.content

    def test_email_constraint(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        customer = next(f for f in files if f.file_name == "Customer.java")
        assert "@Email" in customer.content

    def test_decimal_min_max(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "@DecimalMin" in order.content


class TestXsdGeneration:
    def _config(self, **kwargs):
        return GeneratorConfig(
            package_name="com.example.order",
            schema_type=SchemaType.XSD,
            **kwargs,
        )

    def test_generates_all_types(self):
        files = generate_models(SAMPLE_XSD, self._config())
        names = {f.file_name for f in files}
        assert "Order.java" in names
        assert "Customer.java" in names
        assert "Address.java" in names
        assert "OrderItem.java" in names
        assert "OrderStatus.java" in names

    def test_camel_case_field_names(self):
        files = generate_models(SAMPLE_XSD, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "orderId" in order.content
        assert "totalAmount" in order.content
        assert "orderDate" in order.content

    def test_json_property_for_kebab_case(self):
        files = generate_models(SAMPLE_XSD, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert '@JsonProperty("order-id")' in order.content

    def test_enum_from_restriction(self):
        files = generate_models(SAMPLE_XSD, self._config())
        status = next(f for f in files if f.file_name == "OrderStatus.java")
        assert "public enum OrderStatus" in status.content
        assert "SHIPPED" in status.content

    def test_list_with_max_occurs_unbounded(self):
        files = generate_models(SAMPLE_XSD, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "List<OrderItem>" in order.content

    def test_attribute_field(self):
        files = generate_models(SAMPLE_XSD, self._config())
        customer = next(f for f in files if f.file_name == "Customer.java")
        # The "type" attribute should be renamed to avoid keyword clash
        assert "typeValue" in customer.content or "type" in customer.content

    def test_decimal_type(self):
        files = generate_models(SAMPLE_XSD, self._config())
        order_item = next(f for f in files if f.file_name == "OrderItem.java")
        assert "BigDecimal" in order_item.content

    def test_datetime_type(self):
        files = generate_models(SAMPLE_XSD, self._config())
        order = next(f for f in files if f.file_name == "Order.java")
        assert "LocalDateTime" in order.content


class TestCompilability:
    """Tests to verify generated code is syntactically valid Java."""

    def _config(self):
        return GeneratorConfig(
            package_name="com.test.models",
            schema_type=SchemaType.JSON_SCHEMA,
        )

    def test_all_files_have_package(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        for f in files:
            assert f.content.startswith("package com.test.models;"), f.file_name

    def test_all_classes_have_closing_brace(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        for f in files:
            stripped = f.content.strip()
            assert stripped.endswith("}"), f"Missing closing brace in {f.file_name}"

    def test_no_duplicate_imports(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        for f in files:
            imports = [
                line.strip()
                for line in f.content.split("\n")
                if line.strip().startswith("import ")
            ]
            assert len(imports) == len(set(imports)), f"Duplicate imports in {f.file_name}"

    def test_balanced_braces(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        for f in files:
            opens = f.content.count("{")
            closes = f.content.count("}")
            assert opens == closes, f"Unbalanced braces in {f.file_name}: {opens} {{ vs {closes} }}"

    def test_file_paths_match_package(self):
        files = generate_models(SAMPLE_JSON_SCHEMA, self._config())
        for f in files:
            expected_prefix = "com/test/models/"
            assert f.file_path.startswith(expected_prefix), (
                f"File path {f.file_path} doesn't match package"
            )
