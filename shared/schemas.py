from typing import Literal, Optional

from pydantic import BaseModel


# ---- phase 01: chat-polling ----

class ChatMessage(BaseModel):
    author: str
    content: str
    timestamp: str


class ChatPollingOutput(BaseModel):
    channel_id: str
    messages: list[ChatMessage]


# ---- phase 02: meeting-transcribe ----

class TranscriptSegment(BaseModel):
    speaker: Optional[str] = None
    start: float
    end: float
    text: str


class TranscribeOutput(BaseModel):
    segments: list[TranscriptSegment]


# ---- phase 03: semantic-judge ----

class SemanticJudgeInput(BaseModel):
    source: Literal["meeting", "chat"]
    text: str


class SemanticJudgeOutput(BaseModel):
    is_meaningful: bool
    category: Literal["schedule", "assignee", "scope", "decision", "none"]
    confidence: float
    evidence: str


# ---- phase 04: doc-draft ----

class DocDraftInput(BaseModel):
    judged: SemanticJudgeOutput
    text: str


class StructuredChange(BaseModel):
    task: str
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    type: str


class DocDraftOutput(BaseModel):
    structured: StructuredChange
    doc_text: str


# ---- phase 06: notion-sync ----

class NotionSyncInput(BaseModel):
    structured: StructuredChange
    doc_text: str
