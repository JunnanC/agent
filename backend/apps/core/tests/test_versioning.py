import pytest

from apps.core.versioning import (
    RevisionConflict,
    RevisionInputError,
    assert_revision,
    build_etag,
    next_revision,
    parse_revision,
)


def test_revision_accepts_integer_and_etag_forms() -> None:
    assert parse_revision(3) == 3
    assert parse_revision('"3"') == 3
    assert parse_revision('W/"3"') == 3
    assert build_etag(3) == '"3"'
    assert build_etag(3, weak=True) == 'W/"3"'


def test_revision_rejects_malformed_values() -> None:
    with pytest.raises(RevisionInputError):
        parse_revision("latest")
    with pytest.raises(RevisionInputError):
        parse_revision(-1)


def test_revision_conflict_is_detected_before_write() -> None:
    with pytest.raises(RevisionConflict) as exc_info:
        assert_revision(4, 3)

    assert exc_info.value.expected == 3
    assert exc_info.value.actual == 4
    assert next_revision(4) == 5
