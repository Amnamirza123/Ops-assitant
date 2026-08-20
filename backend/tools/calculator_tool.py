# tools/calculator_tool.py

import math
from langchain_core.tools import tool

# Safe namespace: only math functions/constants are available, nothing
# else — this is what makes eval() safe here (no built-ins, no imports).
SAFE_NAMESPACE = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
    "exp": math.exp, "pow": pow, "abs": abs, "round": round,
    "pi": math.pi, "e": math.e,
    "radians": math.radians, "degrees": math.degrees,
    "factorial": math.factorial,
}


@tool
def calculator(expression: str) -> str:
    """Evaluates a math expression, including scientific functions like
    sin, cos, tan, sqrt, log, and constants like pi and e. Trig functions
    expect radians — convert degrees using radians(x) first if the user
    gives degrees, e.g. sin(radians(180)).
    Use this when the user asks for a calculation, percentage, or any
    arithmetic or scientific math. Input should be a plain math
    expression as a string, e.g. '15 * 0.2', 'sin(radians(180))', or
    'sqrt(144)'.
    """
    try:
        result = eval(expression, {"__builtins__": {}}, SAFE_NAMESPACE)
        if isinstance(result, float):
            result = round(result, 6)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"