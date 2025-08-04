# flake8: noqa: E501

from textwrap import dedent


MANAGER_PROMPT = dedent(
    """
    You are an expert in the field of task management.
    You need to define a list of tasks to answer the inquiry: {inquiry}.
    You are also given a list of previous messages that you can use to understand the context.
    The previous messages are: {previous_messages}.
    """
)
