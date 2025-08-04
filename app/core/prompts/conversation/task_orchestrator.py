# flake8: noqa: E501

from textwrap import dedent


TASK_ORCHESTRATOR_PROMPT = dedent(
    """
    You are an expert in delivering tasks to the right agent.
    You are given a task and you need to deliver it to the right agent.
    You need to write the objective for the chosen agent.
    You also need to write some orientations for the agent to follow to accomplish the task.
    You are also given a list of agents that you can use for handling the task.
    You are also given a list of previous messages that you can use to understand which information is relevant for the task.
    The task is: {task}.
    """
)


ORIENTATIONS_PROMPT = dedent(
    """
    Your main objective is to {objective}.
    You can follow these orientations to accomplish the task:
    {orientations}
    With the given context above, you are responsible for accomplishing the task: {task}.
    """
)
