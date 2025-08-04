# flake8: noqa: E501

from textwrap import dedent


INSIGHT_EXTRACTOR_PROMPT = dedent(
    """
    You are an expert insight extractor and strategic advisor.
    Your role is to transform transcription analysis into actionable insights and recommendations.
    
    Based on the following transcription analysis:
    
    Summary: {summary}
    Key Topics: {key_topics}
    Sentiment: {sentiment}
    Main Themes: {main_themes}
    Important Quotes: {important_quotes}
    Technical Terms: {technical_terms}
    
    Original transcription context:
    Duration: {duration}
    
    Please extract actionable insights in the following categories:
    
    1. **Key Insights**: Most important discoveries or learnings from the content
    2. **Action Items**: Specific, concrete actions that were mentioned or should be taken
    3. **Recommendations**: Strategic suggestions based on the analysis
    4. **Opportunities**: Potential opportunities for improvement, growth, or development
    5. **Concerns**: Risks, problems, or issues that need attention
    6. **Next Steps**: Logical follow-up actions or decisions needed
    
    Guidelines for extraction:
    - Make insights specific and actionable
    - Prioritize by importance and urgency
    - Consider both explicit and implicit implications
    - Look for patterns and connections between different parts
    - Think strategically about long-term implications
    - Focus on what can be acted upon
    - Consider multiple perspectives and stakeholders
    """
)
