# tools/calculator_tool.py

import numexpr
from langchain_core.tools import tool


@tool
def calculator(expression: str) -> str:
    """Evaluates a basic math expression and returns the result.
    Use this when the user asks for a calculation, sum, percentage, or
    any arithmetic. Input should be a plain math expression as a string,
    e.g. '15 * 0.2' or '100 + 250'.
    """ 
    try:
        result = numexpr.evaluate(expression).item()
        if isinstance(result, float):
                result = round(result, 2)
        return str(result)      
    except Exception as e:
        return f"Error evaluating expression: {e}"