import operator
from typing import Any


def reset_when_empty(left: list[Any], right: list[Any]) -> list[Any]:
    """
    Reset the list when it is empty, otherwise merge them

    Args:
        left (list[Any]): The left list
        right (list[Any]): The right list

    Returns:
        list[Any]: The result of the addition

    Notes:
        This function is used to reset the list when it is empty
        and add the right list to the left list
    """
    if not right:
        return []
    return operator.add(left, right)
