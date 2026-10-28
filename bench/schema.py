"""A small JSON Schema subset validator (type, required, properties, additionalProperties: false,
enum, items, minItems, maxItems, minimum, maxLength, pattern). Enough for the strict-output task
without a third-party dependency; the harness ships the schema so anyone can re-check with a full validator."""

from __future__ import annotations

import re

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(value: object, schema: dict, path: str = "$") -> str | None:
    """Return the first error as text, or None when the value conforms."""
    expected_type = schema.get("type")
    if expected_type and not _TYPES[expected_type](value):
        return f"{path}: expected {expected_type}"
    if "enum" in schema and value not in schema["enum"]:
        return f"{path}: {value!r} is not one of {schema['enum']}"
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                return f"{path}: missing required property {name!r}"
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                return f"{path}: unexpected property {extra[0]!r}"
        for name, sub in properties.items():
            if name in value:
                error = validate(value[name], sub, f"{path}.{name}")
                if error:
                    return error
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            return f"{path}: fewer than {schema['minItems']} items"
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            return f"{path}: more than {schema['maxItems']} items"
        for index, element in enumerate(value):
            error = validate(element, schema.get("items", {}), f"{path}[{index}]")
            if error:
                return error
    if isinstance(value, str):
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            return f"{path}: longer than {schema['maxLength']} characters"
        if "pattern" in schema and not re.search(schema["pattern"], value):
            return f"{path}: does not match {schema['pattern']}"
    if _TYPES["number"](value) and "minimum" in schema and value < schema["minimum"]:
        return f"{path}: below minimum {schema['minimum']}"
    return None
