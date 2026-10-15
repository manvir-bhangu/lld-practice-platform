from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar
from app.domain.errors import InvalidSubmission
TEXT_DESIGN_SECTIONS = (
    "assumptions",
    "classes",
    "relationships",
    "key_flows",
    "extensibility",
)


class SubmissionContent(ABC):
    format: ClassVar[str]

    @abstractmethod
    def is_blank(self) -> bool: ...

    @abstractmethod
    def as_text(self) -> str:
        """Plain-text view that any evaluator can read."""

    @abstractmethod
    def to_dict(self) -> dict: ...


@dataclass(frozen=True)
class TextDesign(SubmissionContent):
    format: ClassVar[str] = "text_design"
    sections: dict[str, str] = field(default_factory=dict)
    def __post_init__(self):
        unknown = set(self.sections) - set(TEXT_DESIGN_SECTIONS)
        if unknown:
            raise InvalidSubmission(f"Unknown sections: {', '.join(sorted(unknown))}")
        for name, text in self.sections.items():
            if len(text) > MAX_SECTION_CHARS:
                raise InvalidSubmission(
                    f"Section '{name}' is longer than {MAX_SECTION_CHARS} characters"
                )    
    def is_blank(self) -> bool:
        return not any(v.strip() for v in self.sections.values())

    def as_text(self) -> str:
        parts = []
        for name in TEXT_DESIGN_SECTIONS:
            text = self.sections.get(name, "").strip()
            if text:
                parts.append(f"## {name}\n{text}")
        return "\n\n".join(parts)

    def to_dict(self) -> dict:
        return {"format": self.format, "sections": dict(self.sections)}
    @classmethod
    def from_dict(cls, data: dict) -> "TextDesign":
        sections = data.get("sections", {})
        return cls(sections={str(k): str(v) for k, v in sections.items()})
_CONTENT_TYPES = {TextDesign.format: TextDesign}
MAX_SECTION_CHARS = 5000

def content_from_dict(data: dict) -> SubmissionContent:
    cls = _CONTENT_TYPES.get(data.get("format"))
    if cls is None:
        raise InvalidSubmission(f"Unknown submission format: {data.get('format')}")
    return cls.from_dict(data)