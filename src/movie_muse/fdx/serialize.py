"""Canonical FDX XML serialization. Attribute order and whitespace are stable."""

from __future__ import annotations

import json
from collections.abc import Mapping
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

from movie_muse.fdx.types import MM_NS, MM_PREFIX

NSMAP = {MM_PREFIX: MM_NS}


def qname(local: str, *, ns: str | None = MM_NS) -> str:
    if ns is None:
        return local
    return f"{{{ns}}}{local}"


def local_name(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def namespace_of(tag: str) -> str | None:
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return None


def elem(tag: str, *, text: str | None = None, attrib: Mapping[str, str] | None = None) -> ET.Element:
    node = ET.Element(tag, {key: value for key, value in sorted((attrib or {}).items())})
    if text is not None:
        node.text = text
    return node


def append(parent: ET.Element, child: ET.Element) -> ET.Element:
    parent.append(child)
    return child


def jsonable(value: object) -> object:
    """Convert frozen mappings/tuples into JSON-serializable lists and dicts."""

    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(item) for item in value]
    return value


def dump_json_attr(value: object) -> str:
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_json_attr(raw: str) -> object:
    return json.loads(raw)


def canonical_xml(root: ET.Element) -> bytes:
    """UTF-8 XML with sorted attributes and two-space indentation."""

    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.extend(_emit(root, depth=0))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _emit(node: ET.Element, *, depth: int) -> list[str]:
    indent = "  " * depth
    name = _display_tag(node.tag)
    attrs = "".join(
        f" {_display_attr(key)}={quoteattr(value)}"
        for key, value in sorted(node.attrib.items(), key=lambda item: _display_attr(item[0]))
    )
    children = list(node)
    text = node.text if node.text and node.text.strip() else None
    if not children and text is None:
        return [f"{indent}<{name}{attrs}/>"]
    if not children:
        return [f"{indent}<{name}{attrs}>{escape(text or '')}</{name}>"]
    lines = [f"{indent}<{name}{attrs}>"]
    if text:
        lines.append(f"{indent}  {escape(text)}")
    for child in children:
        lines.extend(_emit(child, depth=depth + 1))
    lines.append(f"{indent}</{name}>")
    return lines


def _display_attr(key: str) -> str:
    ns = namespace_of(key)
    name = local_name(key)
    if ns == MM_NS:
        return f"{MM_PREFIX}:{name}"
    return key


def _display_tag(tag: str) -> str:
    ns = namespace_of(tag)
    name = local_name(tag)
    if ns == MM_NS:
        return f"{MM_PREFIX}:{name}"
    return name


def parse_xml(data: bytes | str) -> ET.Element:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return ET.fromstring(data)
