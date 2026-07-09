"""Registry of external "info" tools that fetch a source on demand.

Six tools share the same shape: the model supplies one string argument, the tool
fetches an external resource (no API key), and the result is recorded as a cited
Source. Describing them declaratively here removes the per-tool duplication that
otherwise spreads across ``tools.py`` (schema), ``decision.py`` (parsing), and
``agent.py`` (dispatch).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .arxiv import ArxivError, fetch_arxiv
from .calculator import CalculatorError, calculate_str
from .convert import ConvertError, convert
from .crossref import CrossRefError, fetch_crossref
from .dictionary import DictionaryError, fetch_definition
from .github import GitHubError, fetch_github
from .models import ActionType
from .news import NewsError, fetch_news
from .openalex import OpenAlexError, fetch_openalex
from .pubmed import PubMedError, fetch_pubmed
from .stock import StockError, fetch_stock_quote
from .weather import WeatherError, fetch_weather
from .wikipedia import WikipediaError, fetch_wikipedia

# A fetch callable takes (argument, per-source char limit) -> (source_url, content).
FetchFn = Callable[[str, int], tuple[str, str]]


@dataclass(frozen=True)
class InfoTool:
    """Declarative description of a single-argument, source-producing tool."""

    name: str               # tool/action name advertised to the model
    action: ActionType      # the parsed ActionType
    arg_field: str          # AgentDecision attribute that carries the argument
    schema_param: str       # JSON parameter name the model fills in
    description: str        # tool description for the model
    param_description: str  # parameter description for the model
    fetch: FetchFn          # performs the fetch -> (url, content)
    error: type[Exception]  # raised by ``fetch`` on failure

    def to_schema(self) -> dict[str, Any]:
        """Build the OpenAI/Gemini function-calling schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        self.schema_param: {
                            "type": "string",
                            "description": self.param_description,
                        },
                        "reasoning": {
                            "type": "string",
                            "description": f"Why {self.name} is needed.",
                        },
                    },
                    "required": [self.schema_param],
                },
            },
        }


INFO_TOOLS: tuple[InfoTool, ...] = (
    InfoTool(
        name="get_weather",
        action=ActionType.GET_WEATHER,
        arg_field="location",
        schema_param="location",
        description="Get the current weather for a specific location.",
        param_description="The city or location name to get weather for.",
        fetch=lambda arg, _limit: fetch_weather(arg),
        error=WeatherError,
    ),
    InfoTool(
        name="get_stock",
        action=ActionType.GET_STOCK,
        arg_field="symbol",
        schema_param="symbol",
        description=(
            "Get the latest available stock/index quote (price, daily range, "
            "volume) for a ticker symbol, e.g. 'AAPL', '^GSPC', 'BTC-USD'."
        ),
        param_description="The ticker symbol, e.g. 'AAPL' or '^GSPC'.",
        fetch=lambda arg, _limit: fetch_stock_quote(arg),
        error=StockError,
    ),
    InfoTool(
        name="get_wikipedia",
        action=ActionType.GET_WIKIPEDIA,
        arg_field="topic",
        schema_param="topic",
        description=(
            "Look up an encyclopedic summary of a topic from Wikipedia. Good "
            "for definitions, background, and well-established facts."
        ),
        param_description="The topic or article title to look up.",
        fetch=lambda arg, limit: fetch_wikipedia(arg, max_chars=limit),
        error=WikipediaError,
    ),
    InfoTool(
        name="arxiv_search",
        action=ActionType.ARXIV_SEARCH,
        arg_field="paper_query",
        schema_param="query",
        description=(
            "Search arXiv for academic papers and read their abstracts. Use "
            "for scientific, technical, or research-paper questions."
        ),
        param_description="The topic or keywords to search arXiv for.",
        fetch=lambda arg, _limit: fetch_arxiv(arg),
        error=ArxivError,
    ),
    InfoTool(
        name="get_news",
        action=ActionType.GET_NEWS,
        arg_field="news_query",
        schema_param="query",
        description=(
            "Find recent news/stories about a topic (via Hacker News). Use "
            "for current events and trending tech discussions."
        ),
        param_description="The topic to find recent stories about.",
        fetch=lambda arg, _limit: fetch_news(arg),
        error=NewsError,
    ),
    InfoTool(
        name="get_github",
        action=ActionType.GET_GITHUB,
        arg_field="repo",
        schema_param="repo",
        description=(
            "Look up a GitHub repository's metadata (stars, language, "
            "license, latest release). Use for software/library questions."
        ),
        param_description="Repository as 'owner/name' or a GitHub URL.",
        fetch=lambda arg, _limit: fetch_github(arg),
        error=GitHubError,
    ),
    InfoTool(
        name="get_dictionary",
        action=ActionType.GET_DICTIONARY,
        arg_field="word",
        schema_param="word",
        description="Look up the definition(s) and part of speech of an English word.",
        param_description="The single English word to define.",
        fetch=lambda arg, _limit: fetch_definition(arg),
        error=DictionaryError,
    ),
    InfoTool(
        name="crossref_search",
        action=ActionType.CROSSREF_SEARCH,
        arg_field="doi_query",
        schema_param="query",
        description=(
            "Search CrossRef for peer-reviewed/scholarly works (title, authors, "
            "year, DOI). Use for academic or citation-grade sources."
        ),
        param_description="The topic, title, or keywords to search CrossRef for.",
        fetch=lambda arg, _limit: fetch_crossref(arg),
        error=CrossRefError,
    ),
    InfoTool(
        name="pubmed_search",
        action=ActionType.PUBMED_SEARCH,
        arg_field="pubmed_query",
        schema_param="query",
        description=(
            "Search PubMed for peer-reviewed biomedical/clinical literature "
            "(title, authors, journal, year, PMID). Use for medical, health, "
            "biology, or life-sciences questions that need citation-grade sources."
        ),
        param_description="The topic, disease, drug, or keywords to search PubMed for.",
        fetch=lambda arg, _limit: fetch_pubmed(arg),
        error=PubMedError,
    ),
    InfoTool(
        name="openalex_search",
        action=ActionType.OPENALEX_SEARCH,
        arg_field="openalex_query",
        schema_param="query",
        description=(
            "Search OpenAlex, a large open index of scholarly works across all "
            "disciplines (title, authors, venue, year, DOI). Use as a general "
            "academic search when arXiv/PubMed/CrossRef are too narrow."
        ),
        param_description="The topic, title, or keywords to search OpenAlex for.",
        fetch=lambda arg, _limit: fetch_openalex(arg),
        error=OpenAlexError,
    ),
)

INFO_TOOL_BY_ACTION: dict[ActionType, InfoTool] = {tool.action: tool for tool in INFO_TOOLS}
INFO_TOOL_BY_NAME: dict[str, InfoTool] = {tool.name: tool for tool in INFO_TOOLS}


@dataclass(frozen=True)
class NoteTool:
    """A single-argument tool whose result is a trusted local note (not a source).

    Used for the deterministic local helpers (calculator, unit/currency convert)
    that contribute a fact to the agent's notes rather than a fetched source.
    """

    name: str
    action: ActionType
    arg_field: str
    schema_param: str
    description: str
    param_description: str
    compute: Callable[[str], str]   # returns the result string; raises ``error``
    error: type[Exception]
    note_format: str                # e.g. "calculate({arg}) = {result}"

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        self.schema_param: {
                            "type": "string",
                            "description": self.param_description,
                        },
                        "reasoning": {
                            "type": "string",
                            "description": f"Why {self.name} is needed.",
                        },
                    },
                    "required": [self.schema_param],
                },
            },
        }

    def make_note(self, arg: str) -> str:
        """Compute the result and format the trusted note (may raise ``error``)."""
        return self.note_format.format(arg=arg, result=self.compute(arg))


NOTE_TOOLS: tuple[NoteTool, ...] = (
    NoteTool(
        name="calculate",
        action=ActionType.CALCULATE,
        arg_field="expression",
        schema_param="expression",
        description=(
            "Evaluate a basic arithmetic expression (e.g. percentages, growth, "
            "unit conversions) when the answer needs a precise number."
        ),
        param_description="Arithmetic expression, e.g. '(120-90)/90*100'.",
        compute=calculate_str,
        error=CalculatorError,
        note_format="calculate({arg}) = {result}",
    ),
    NoteTool(
        name="convert",
        action=ActionType.CONVERT,
        arg_field="conversion",
        schema_param="expression",
        description=(
            "Convert between units or currencies, e.g. '100 USD to EUR', "
            "'10 km to miles', '32 F to C'."
        ),
        param_description="Conversion like 'AMOUNT FROM to TO'.",
        compute=convert,
        error=ConvertError,
        note_format="convert({arg}) = {result}",
    ),
)

NOTE_TOOL_BY_ACTION: dict[ActionType, NoteTool] = {tool.action: tool for tool in NOTE_TOOLS}
