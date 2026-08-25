import pytest
from pydantic import ValidationError

from shiftchain.frozen_data import candidate_context, frozen_repository, intent_for
from shiftchain.models import StructuredIntent
from shiftchain.parser import CandidateBoundaryError, GeminiIntentParser


def test_schema_forbids_extra_fields() -> None:
    payload = intent_for("EVT-001").model_dump(mode="json")
    payload["model_decides_validity"] = True
    with pytest.raises(ValidationError):
        StructuredIntent.model_validate(payload)


def test_candidate_boundary_rejects_hallucinated_id() -> None:
    repository = frozen_repository()
    context = candidate_context(repository, "EVT-001")
    hallucinated = intent_for("EVT-001").model_copy(update={"to_worker_id": "W-999"})
    with pytest.raises(CandidateBoundaryError):
        GeminiIntentParser.enforce_candidate_boundary(hallucinated, context)


def test_ambiguity_fixture_has_two_worker_and_shift_possibilities() -> None:
    context = candidate_context(frozen_repository(), "AMB-001")
    assert "W-002" in context.worker_candidates and "W-006" in context.worker_candidates
    assert len(context.shift_candidates) > 4
    assert intent_for("AMB-001").ambiguities


@pytest.mark.parametrize("event_id", ["EVT-001", "EVT-002", "EVT-003", "EVT-004", "AMB-001"])
def test_all_fixtures_round_trip_schema(event_id: str) -> None:
    intent = intent_for(event_id)
    assert StructuredIntent.model_validate_json(intent.model_dump_json()) == intent

