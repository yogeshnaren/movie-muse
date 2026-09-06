"""Invalid structured extraction repairs once, then fails closed."""

from __future__ import annotations

import pytest

from movie_muse.film_ir.api import ExtractionRepairError, repair_extraction_output
from movie_muse.model_router.api import StructuredOutputError


def test_missing_method_is_repaired() -> None:
    repaired = repair_extraction_output(
        {"entities": [{"name": "Harbor", "kind": "location"}]}
    )
    assert repaired["method"] == "repaired"
    assert repaired["assumptions"]
    assert repaired["uncertainty"] == "repaired"
    assert repaired["entities"] == [{"name": "Harbor", "kind": "location"}]


def test_chain_of_thought_fails_closed() -> None:
    with pytest.raises(StructuredOutputError):
        repair_extraction_output(
            {
                "entities": [{"name": "Ada", "kind": "character"}],
                "chain_of_thought": "secret reasoning",
            }
        )


def test_missing_entities_cannot_be_repaired() -> None:
    with pytest.raises(ExtractionRepairError):
        repair_extraction_output({"method": "bad"})


def test_blank_entity_row_fails() -> None:
    with pytest.raises(ExtractionRepairError):
        repair_extraction_output({"entities": [{"name": "", "kind": "character"}]})
