from enum import Enum


class Intention(str, Enum):
    """Intention"""
    GREET = "greet"
    ASK = "ask"
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    REVIEW = "review"
    REPORT = "report"
    RECOMMEND = "recommend"
    OTHER = "other"


class Agent(str, Enum):
    """Agent"""
    DATA_COLLECTOR = "data_collector"
    MANAGER = "manager"
    TASK_ORCHESTRATOR = "task_orchestrator"
    INTENT_SEEKER = "intent_seeker"
    TOUCHPOINT = "touchpoint"


class WorkerAgent(str, Enum):
    """Worker agent"""
    DATA_COLLECTOR = "data_collector"
