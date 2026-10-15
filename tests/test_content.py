import pytest

from app.domain.content import TextDesign, content_from_dict
from app.domain.errors import InvalidSubmission


def test_unknown_section_rejected():
    with pytest.raises(InvalidSubmission):
        TextDesign(sections={"random": "x"})


def test_overlong_section_rejected():
    with pytest.raises(InvalidSubmission):
        TextDesign(sections={"classes": "x" * 5001})


def test_content_roundtrip():
    original = TextDesign(sections={"classes": "A, B"})
    assert content_from_dict(original.to_dict()) == original


def test_unknown_format_rejected():
    with pytest.raises(InvalidSubmission):
        content_from_dict({"format": "uml_diagram"})