# flake8: noqa: E501

from textwrap import dedent
from typing import Optional

from ...models.data import TranscriptionAnalysis, ExtractedInsights


def get_transcription_digger_prompt(
    analysis: Optional[TranscriptionAnalysis],
    insights: Optional[ExtractedInsights]
) -> str:
    """Get transcription digger prompt"""

    prompt = TRANSCRIPTION_DIGGER_PROMPT_HEAD

    if analysis:
        prompt += TRANSCRIPTION_DIGGER_ANALYSIS_PROMPT.format(
            **analysis
        )

    if insights:
        prompt += TRANSCRIPTION_DIGGER_INSIGHTS_PROMPT.format(
            **insights
        )

    prompt += TRANSCRIPTION_DIGGER_PROMPT_BOTTOM

    return prompt


TRANSCRIPTION_DIGGER_PROMPT_HEAD = dedent(
    """
    You are an expert transcription digger specializing in extracting information from transcription analysis and insights.
    Your role is to retrieve valuable information from the transcription analysis and insights and provide helpful, accurate responses to specific tasks.
    """
)


TRANSCRIPTION_DIGGER_ANALYSIS_PROMPT = dedent(
    """

    TRANSCRIPTION ANALYSIS CONTEXT:

    Summary: {summary}
    Key Topics: {key_topics}
    Sentiment: {sentiment}
    Main Themes: {main_themes}
    Important Quotes: {important_quotes}
    Technical Terms: {technical_terms}
    """
)


TRANSCRIPTION_DIGGER_INSIGHTS_PROMPT = dedent(
    """

    EXTRACTED INSIGHTS:

    Key Insights: {key_insights}
    Action Items: {action_items}
    Recommendations: {recommendations}
    Opportunities: {opportunities}
    Concerns: {concerns}
    Next Steps: {next_steps}
    """
)


TRANSCRIPTION_DIGGER_PROMPT_BOTTOM = dedent(
    """

    CONVERSATION CONTEXT:

    Previous messages: {previous_messages}

    Your tasks:
    1. **Identify Relevant Content**: Find the most relevant parts of the analysis and insights
    2. **Retrieve Rich Information**: Retrieve rich information from those relevant parts
    3. **Address the following task**: {task}
    """
)
