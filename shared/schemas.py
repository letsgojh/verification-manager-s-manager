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


# ---- phase 05: pm-approval ----

class PmApprovalOutput(BaseModel):
    decision: Literal["approved", "rejected", "held"]
    structured: StructuredChange
    doc_text: str


# ---- phase 06: notion-sync ----

class NotionSyncInput(BaseModel):
    structured: StructuredChange
    doc_text: str


# ---- phase 09: deadline-remind ----

class DeadlineRemindInput(BaseModel):
    task: str
    assignee: str
    due_date: str  # YYYY-MM-DD
    type: str


class ChecklistItem(BaseModel):
    item: str
    done: bool


class DeadlineRemindOutput(BaseModel):
    skipped: bool = False
    days_left: Optional[int] = None
    check_in_message: Optional[str] = None
    assignee_reply: Optional[str] = None
    clarifying_question: Optional[str] = None
    assignee_reply_2: Optional[str] = None
    checklist: Optional[list[ChecklistItem]] = None
    assessment: Optional[Literal["on_track", "at_risk", "no_reply"]] = None
    notion_synced: bool = False
    closing_message: Optional[str] = None
