"""
ALang serialization utilities.

Provides helpers for rendering and serializing ALang terms (Lisp-like
abstract syntax) for debugging, logging, and display outside the UI context.
"""

from typing import Any


def alang_to_str(term: Any) -> str:
    """
    Render an ALang term as a pretty string.
    
    Expects the term to be a dict-like structure that mirrors ALang
    constructors used internally. Falls back to repr() if the term
    is not recognizable.
    
    Args:
        term: Any Python value, typically a dict, list, str, or primitive.
    
    Returns:
        A string representation of the ALang term.
    
    Examples:
        >>> alang_to_str({":inform": "Hello"})
        ':inform Hello'
        >>> alang_to_str({":warning": [{":level": 3}]})
        ':warning [{:level 3}]'
    """
    if isinstance(term, dict):
        # Pick a known constructor key if present (keys starting with ':')
        for k in term:
            if k.startswith(":"):
                return f"{k} {alang_to_str(term[k])}"
        # Fallback: show the full map
        return "{" + " ".join(f"{k}:{alang_to_str(v)}" for k, v in term.items()) + "}"
    if isinstance(term, list):
        return "[" + " ".join(alang_to_str(e) for e in term) + "]"
    if isinstance(term, str):
        return f'"{term}"'
    return str(term)
