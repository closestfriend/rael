"""Bounded local tools. No shell, eval(), filesystem writes, or network access."""

import ast
import math
import operator
from typing import Any

from agentlab.core.models import ToolSpec


class Calculator:
    spec = ToolSpec(
        name="calculator",
        description="Evaluate arithmetic (+, -, *, /, %, parentheses).",
        parameters={
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
            "additionalProperties": False,
        },
    )

    def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        expression = arguments.get("expression")
        if (
            set(arguments) != {"expression"}
            or not isinstance(expression, str)
            or len(expression) > 200
        ):
            raise ValueError("Expected one expression string, at most 200 characters")
        operations = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Mod: operator.mod,
        }

        def calculate(node):
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                value = node.value
            elif isinstance(node, ast.BinOp) and type(node.op) in operations:
                value = operations[type(node.op)](calculate(node.left), calculate(node.right))
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = calculate(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
            else:
                raise ValueError("Only bounded arithmetic is supported")
            if abs(value) > 1e15 or not math.isfinite(value):
                raise ValueError("Result exceeds calculator range")
            return value

        try:
            tree = ast.parse(expression, mode="eval")
            if len(list(ast.walk(tree))) > 80:
                raise ValueError("Expression is too complex")
            return {"value": calculate(tree.body)}
        except (SyntaxError, ArithmeticError, RecursionError) as exc:
            raise ValueError("Invalid arithmetic expression") from exc


class SearchStub:
    spec = ToolSpec(
        name="search",
        description="Search the task's fixed reference corpus; returns source IDs.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    )

    def __init__(self, references: list[dict[str, Any]]):
        self.references = references

    def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = arguments.get("query")
        if set(arguments) != {"query"} or not isinstance(query, str) or not query.strip():
            raise ValueError("Expected a nonempty query string")
        terms = query.lower().split()
        return {
            "sources": [r for r in self.references if any(t in str(r).lower() for t in terms)][:10]
        }


def tool_registry(references: list[dict[str, Any]]) -> dict[str, Any]:
    return {"calculator": Calculator(), "search": SearchStub(references)}
