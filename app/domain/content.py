from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

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