from enum import Enum


class Intention(str, Enum):
    """Intention"""
    GREET = "greet"
    ANALYZE = "analyze"
    QUESTION = "question"
    SUMMARIZE = "summarize"
    EXTRACT_INSIGHTS = "extract_insights"
    EXTRACT_ACTIONS = "extract_actions"
    FIND_TOPICS = "find_topics"
    COMPARE = "compare"
    EVALUATE = "evaluate"
    OTHER = "other"


class Agent(str, Enum):
    """Agent"""
    INTENT_SEEKER = "intent_seeker"
    MANAGER = "manager"
    TASK_ORCHESTRATOR = "task_orchestrator"
    CONVERSATION_HANDLER = "conversation_handler"
    TOUCHPOINT = "touchpoint"


class WorkerAgent(str, Enum):
    """Worker agent"""
    CONVERSATION_HANDLER = "conversation_handler"
