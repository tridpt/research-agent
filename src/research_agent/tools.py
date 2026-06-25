"""Native tool-calling schemas.

These describe the agent's actions in the OpenAI / Gemini function-calling
format (a list of ``{"type": "function", "function": {...}}`` specs). The model
returns a structured ``tool_call`` instead of free-form JSON text, which is more
reliable than JSON-mode prompting.

The "core" tools (search/read/finish/calculate/now/convert/read_pdf) are defined
explicitly here; the single-argument external info tools (weather, stock,
Wikipedia, arXiv, news, GitHub) are generated from ``tool_registry`` so their
schema, parsing, and dispatch stay defined in one place.
"""
from __future__ import annotations

from typing import Any

from .tool_registry import INFO_TOOLS

# Tools with bespoke shapes or local (non-fetch) behavior.
CORE_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Run a web search to find sources relevant to the question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The web search query to run.",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why this search helps answer the question.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Fetch and read the full content of a URL from the search results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch and read.",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why this source is worth reading.",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Stop researching and synthesize the final report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Why there is enough information to finish.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Evaluate a basic arithmetic expression (e.g. percentages, growth, "
                "unit conversions) when the answer needs a precise number."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Arithmetic expression, e.g. '(120-90)/90*100'.",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why this calculation is needed.",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "now",
            "description": "Get the current date and time (useful for 'latest', 'today', age, recency).",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Why the current date/time is needed.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert",
            "description": (
                "Convert between units or currencies, e.g. '100 USD to EUR', "
                "'10 km to miles', '32 F to C'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Conversion like 'AMOUNT FROM to TO'.",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why this conversion is needed.",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_pdf",
            "description": (
                "Read one local PDF explicitly selected by the user. Only use an "
                "exact path listed in the approved-PDF instruction."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute path to the local PDF file.",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why this PDF file is needed.",
                    },
                },
                "required": ["path"],
            },
        },
    },
]

# The canonical tool specifications advertised to the model: core tools plus the
# registry-defined external info tools (weather, stock, Wikipedia, arXiv, ...).
TOOL_SCHEMAS: list[dict[str, Any]] = CORE_TOOL_SCHEMAS + [tool.to_schema() for tool in INFO_TOOLS]
