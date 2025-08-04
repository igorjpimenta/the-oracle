from typing import TypedDict, Optional


class CollectedData(TypedDict):
    """Collected data"""
    data: str
    notes: str


class TranscriptionData(TypedDict):
    """Transcription data structure"""
    transcription_id: str
    text: str
    duration: Optional[float]
    language: Optional[str]
    metadata: Optional[dict]


class TranscriptionAnalysis(TypedDict):
    """Analysis results from transcription"""
    summary: str
    key_topics: list[str]
    sentiment: str
    main_themes: list[str]
    important_quotes: list[str]
    technical_terms: list[str]


class ExtractedInsights(TypedDict):
    """Actionable insights from transcription"""
    key_insights: list[str]
    action_items: list[str]
    recommendations: list[str]
    opportunities: list[str]
    concerns: list[str]
    next_steps: list[str]
