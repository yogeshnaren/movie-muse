"""Shared canned structured outputs. No network. No chain-of-thought."""

from __future__ import annotations

from typing import Any

DEFAULT_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "generate_text": {
        "type": "object",
        "required": ["text", "method", "assumptions", "uncertainty"],
        "additionalProperties": False,
        "properties": {
            "text": {"type": "string"},
            "method": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "uncertainty": {"type": "string"},
        },
    },
    "extract_structure": {
        "type": "object",
        "required": ["entities", "method", "assumptions", "uncertainty"],
        "additionalProperties": False,
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "kind"],
                    "properties": {
                        "name": {"type": "string"},
                        "kind": {"type": "string"},
                    },
                },
            },
            "method": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "uncertainty": {"type": "string"},
        },
    },
    "calculate_production": {
        "type": "object",
        "required": ["estimated_days", "estimated_cost", "method", "assumptions", "uncertainty"],
        "additionalProperties": False,
        "properties": {
            "estimated_days": {"type": "number"},
            "estimated_cost": {"type": "number"},
            "method": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "uncertainty": {"type": "string"},
        },
    },
    "retrieve": {
        "type": "object",
        "required": ["passages", "method", "assumptions", "uncertainty"],
        "additionalProperties": False,
        "properties": {
            "passages": {"type": "array", "items": {"type": "string"}},
            "method": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "uncertainty": {"type": "string"},
        },
    },
    "propose_alternatives": {
        "type": "object",
        "required": ["alternatives", "method", "assumptions", "uncertainty"],
        "additionalProperties": False,
        "properties": {
            "alternatives": {"type": "array", "items": {"type": "string"}},
            "method": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "uncertainty": {"type": "string"},
        },
    },
    "propose_structured_ops": {
        "type": "object",
        "required": ["operations", "method", "assumptions", "uncertainty"],
        "additionalProperties": False,
        "properties": {
            "operations": {"type": "array", "items": {"type": "object"}},
            "method": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "uncertainty": {"type": "string"},
        },
    },
    "experience": {
        "type": "object",
        "required": ["reading", "method", "assumptions", "uncertainty"],
        "additionalProperties": False,
        "properties": {
            "reading": {"type": "string"},
            "method": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "uncertainty": {"type": "string"},
        },
    },
    "script_suggest": {
        "type": "object",
        "required": ["suggestion", "method", "assumptions", "uncertainty"],
        "additionalProperties": False,
        "properties": {
            "suggestion": {"type": "string"},
            "method": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "uncertainty": {"type": "string"},
        },
    },
}


def canned_output(capability: str, *, source: str) -> dict[str, Any]:
    method = source
    assumptions = [f"canned_{source}", "not_a_human_sample"]
    uncertainty = "deterministic_fixture"
    catalog: dict[str, dict[str, Any]] = {
        "generate_text": {
            "text": "INT. WRITERS ROOM - DAY\nA creator keeps authorship.",
            "method": method,
            "assumptions": assumptions,
            "uncertainty": uncertainty,
        },
        "extract_structure": {
            "entities": [{"name": "Ada", "kind": "character"}],
            "method": method,
            "assumptions": assumptions,
            "uncertainty": uncertainty,
        },
        "calculate_production": {
            "estimated_days": 12,
            "estimated_cost": 48000,
            "method": method,
            "assumptions": assumptions,
            "uncertainty": uncertainty,
        },
        "retrieve": {
            "passages": ["Permitted local fixture passage."],
            "method": method,
            "assumptions": assumptions,
            "uncertainty": uncertainty,
        },
        "propose_alternatives": {
            "alternatives": ["Keep the scene interior.", "Move the reveal one page later."],
            "method": method,
            "assumptions": assumptions,
            "uncertainty": uncertainty,
        },
        "propose_structured_ops": {
            "operations": [{"op": "update_block", "target": "heading", "payload": {"text": "INT. ROOM - NIGHT"}}],
            "method": method,
            "assumptions": assumptions,
            "uncertainty": uncertainty,
        },
        "experience": {
            "reading": "The scene feels claustrophobic and authored.",
            "method": method,
            "assumptions": assumptions,
            "uncertainty": uncertainty,
        },
        "script_suggest": {
            "suggestion": "Let the silence carry the cut.",
            "method": method,
            "assumptions": assumptions,
            "uncertainty": uncertainty,
        },
    }
    if capability not in catalog:
        return {
            "text": "",
            "method": method,
            "assumptions": assumptions,
            "uncertainty": uncertainty,
        }
    return dict(catalog[capability])
