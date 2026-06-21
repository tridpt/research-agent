"""Native tool-calling schemas.

These describe the agent's actions in the OpenAI / Gemini function-calling
format (a list of ``{"type": "function", "function": {...}}`` specs). The model
returns a structured ``tool_call`` instead of free-form JSON text, which is more
reliable than JSON-mode prompting.
"""
from __future__ import annotations

from typing import Any

# The canonical tool specifications advertised to the model.
TOOL_SCHEMAS: list[dict[str, Any]] = [
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
            "name": "read_pdf",
            "description": "Read the text content of a local PDF file.",
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
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a specific location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city or location name to get weather for.",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why the weather data is needed.",
                    },
                },
                "required": ["location"],
            },
        },
    },
]
