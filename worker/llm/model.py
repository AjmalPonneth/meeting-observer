from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ActionItem:
    owner: str | None = None
    task: str = ""
    due: str | None = None
    status: str = "pending"


@dataclass(slots=True)
class TimelineItem:
    event: str = ""
    owner: str | None = None
    deadline: str | None = None


@dataclass(slots=True)
class Participant:
    name: str = ""
    role: str | None = None


@dataclass(slots=True)
class MeetingSummary:
    summary: str = ""
    decisions: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    pending_topics: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
    participants: list[Participant] = field(default_factory=list)
    timeline: list[TimelineItem] = field(default_factory=list)

    @classmethod
    def from_json(cls, raw: str) -> MeetingSummary:
        cleaned = extract_json_object(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return cls()

        if not isinstance(data, dict):
            return cls()

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MeetingSummary:
        return cls(
            summary=str(data.get("summary") or ""),
            decisions=as_str_list(data.get("decisions")),
            action_items=[
                ActionItem(
                    owner=item.get("owner"),
                    task=str(item.get("task") or ""),
                    due=item.get("due"),
                    status=str(item.get("status") or "pending"),
                )
                for item in as_dict_list(data.get("action_items"))
            ],
            blockers=as_str_list(data.get("blockers")),
            risks=as_str_list(data.get("risks")),
            pending_topics=as_str_list(data.get("pending_topics")),
            open_questions=as_str_list(data.get("open_questions")),
            follow_ups=as_str_list(data.get("follow_ups")),
            participants=[
                Participant(
                    name=str(item.get("name") or ""),
                    role=item.get("role"),
                )
                for item in as_dict_list(data.get("participants"))
            ],
            timeline=[
                TimelineItem(
                    event=str(item.get("event") or ""),
                    owner=item.get("owner"),
                    deadline=item.get("deadline"),
                )
                for item in as_dict_list(data.get("timeline"))
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


def as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    return [str(item) for item in value if item is not None]


def as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, dict)]


def extract_json_object(raw: str) -> str:
    text = raw.strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return text
    return text[start : end + 1]
