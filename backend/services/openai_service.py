"""Azure OpenAI service for LLM and embeddings."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional
from openai import AzureOpenAI, OpenAI

from config import Config

logger = logging.getLogger(__name__)


class AzureOpenAIService:
    """Service for Azure OpenAI operations."""
    
    _chat_client: Optional[AzureOpenAI] = None
    _signal_chat_client: Optional[AzureOpenAI] = None
    _embedding_client: Optional[AzureOpenAI] = None
    
    @classmethod
    def get_chat_client(cls) -> AzureOpenAI:
        """Get or create AzureOpenAI client for chat/completions."""
        if cls._chat_client is None:
            cls._chat_client = AzureOpenAI(
                api_version=Config.AZURE_OPENAI_API_VERSION,
                azure_endpoint=cls._clean_endpoint(Config.AZURE_OPENAI_ENDPOINT),
                api_key=Config.AZURE_OPENAI_API_KEY,
            )
        return cls._chat_client

    @classmethod
    def get_signal_chat_client_and_model(cls) -> tuple[Any, str]:
        """Get the client and model deployment name for generating the Signal Daily Brief."""
        # Use overrides if configured; otherwise fall back to default chat configuration
        api_key = Config.SIGNAL_AZURE_OPENAI_API_KEY or Config.AZURE_OPENAI_API_KEY
        endpoint = Config.SIGNAL_AZURE_OPENAI_ENDPOINT or Config.AZURE_OPENAI_ENDPOINT
        api_version = Config.SIGNAL_AZURE_OPENAI_API_VERSION or Config.AZURE_OPENAI_API_VERSION
        deployment = Config.SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME or Config.AZURE_OPENAI_DEPLOYMENT_NAME

        # If no custom endpoint/key is configured, reuse the default chat client
        if (
            not Config.SIGNAL_AZURE_OPENAI_API_KEY
            and not Config.SIGNAL_AZURE_OPENAI_ENDPOINT
            and not Config.SIGNAL_AZURE_OPENAI_API_VERSION
        ):
            return cls.get_chat_client(), deployment

        if cls._signal_chat_client is None:
            # Auto-detect if we should use standard OpenAI compatible client (e.g. for Serverless/Catalog models)
            # Standard OpenAI client is initialized if the endpoint contains "services.ai.azure.com" or ends with "/v1" or "/v1/"
            is_openai_compatible = False
            if endpoint:
                cleaned_ep = endpoint.lower().strip()
                if "services.ai.azure.com" in cleaned_ep or cleaned_ep.endswith("/v1") or cleaned_ep.endswith("/v1/"):
                    is_openai_compatible = True

            if is_openai_compatible:
                cls._signal_chat_client = OpenAI(
                    base_url=endpoint,
                    api_key=api_key,
                )
            else:
                cls._signal_chat_client = AzureOpenAI(
                    api_version=api_version,
                    azure_endpoint=cls._clean_endpoint(endpoint),
                    api_key=api_key,
                )
        return cls._signal_chat_client, deployment
    
    @classmethod
    def get_embedding_client(cls) -> AzureOpenAI:
        """Get or create AzureOpenAI client for embeddings."""
        if cls._embedding_client is None:
            cls._embedding_client = AzureOpenAI(
                api_version=Config.AZURE_OPENAI_EMBEDDING_API_VERSION,
                azure_endpoint=cls._clean_endpoint(Config.AZURE_OPENAI_ENDPOINT),
                api_key=Config.AZURE_OPENAI_API_KEY,
            )
        return cls._embedding_client
    
    @classmethod
    def generate_embedding(cls, text: str) -> list[float]:
        """Generate embedding for text using text-embedding-3-large."""
        client = cls.get_embedding_client()
        
        # Truncate text if too long (model has 8k token limit)
        # Roughly 4 chars per token, so ~32k chars is safe
        if len(text) > 30000:
            text = text[:30000]
        
        response = client.embeddings.create(
            input=text,
            model=Config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME,
        )
        
        return response.data[0].embedding

    @staticmethod
    def _clean_endpoint(endpoint: str | None) -> str | None:
        """Normalize Azure endpoint to avoid duplicate /openai segments."""
        if not endpoint:
            return endpoint
        cleaned = endpoint.strip().rstrip("/")
        # Remove trailing /openai if present
        if cleaned.endswith("/openai"):
            cleaned = cleaned[: -len("/openai")]
        # Remove trailing /v1 if present
        if cleaned.endswith("/v1"):
            cleaned = cleaned[: -len("/v1")]
        return cleaned
    
    @classmethod
    def enrich_bookmark(
        cls,
        url: str,
        title: str,
        content: str,
        user_notes: str | None = None,
        folders: list[str] | None = None,
        use_nano_model: bool = False,
    ) -> dict:
        """
        Enrich bookmark with LLM analysis.
        
        Returns dict with:
        - clean_title
        - ai_summary
        - auto_tags
        - intent_type
        - technical_level
        - content_type
        - key_quotes
        """
        client = cls.get_chat_client()
        
        # Smart truncation: first 2000 + last 2000 chars to capture intro and conclusion
        if content and len(content) > 4000:
            first_part = content[:2000]
            last_part = content[-2000:]
            content = f"{first_part}\n\n[... middle content truncated ...]\n\n{last_part}"
        
        prompt = f"""Analyze this bookmarked article and provide structured metadata.
        If the content is missing or sparse, use the URL and title to infer the most likely metadata.

        CONTEXT:
        URL: {url}
        Title: {title or 'Unknown'}
        Content: {content or 'No content extracted'}
        User Notes: {user_notes or 'None provided'}
        Available Folders: {", ".join(folders) if folders else "None created yet"}

        TASK:
        Provide a JSON object with strictly these fields:
        1. "clean_title": A clean, concise title (max 60 chars). Remove clickbait or site names if redundant.
        2. "ai_summary": A single, dense summary (max 220 chars). Focus on "What is this?" and "Why save it?". No fluff.
        3. "auto_tags": Array (3-5 items). Lowercase, hyphenated (e.g. "ai-agents", "python-dev").
        4. "intent_type": EXACTLY one of: ["reference", "tutorial", "inspiration", "deep-dive", "tool"]
        5. "technical_level": EXACTLY one of: ["beginner", "intermediate", "advanced", "general"]
        6. "content_type": EXACTLY one of: ["article", "documentation", "video", "tool", "paper", "other"]
        7. "key_quotes": Array (0-3 short, impactful quotes). Leave empty if no specific quotes stand out.
        8. "suggested_folder": EXACT NAME from 'Available Folders' or null if no fit.

        OUTPUT FORMAT:
        Return ONLY valid JSON. No markdown, no pre-amble, no code blocks."""

        deployment_name = (
            Config.AZURE_OPENAI_NANO_DEPLOYMENT_NAME
            if use_nano_model and Config.AZURE_OPENAI_NANO_DEPLOYMENT_NAME
            else Config.AZURE_OPENAI_DEPLOYMENT_NAME
        )

        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that analyzes web content "
                        "and provides structured metadata. Always respond with "
                        "valid JSON only."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=1000,
            response_format={"type": "json_object"},
        )
        
        result_text = response.choices[0].message.content
        
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # If parsing fails, return defaults
            result = {
                "clean_title": title[:60] if title else "Untitled",
                "ai_summary": "No summary available.",
                "auto_tags": [],
                "intent_type": "reference",
                "technical_level": "general",
                "content_type": "article",
                "key_quotes": [],
                "suggested_folder": None,
            }
        
        # Validate and sanitize the result
        validated = {
            "clean_title": str(result.get("clean_title", title or "Untitled"))[:60],
            "ai_summary": str(result.get("ai_summary", ""))[:220],
            "auto_tags": [str(tag).lower().replace(" ", "-") for tag in result.get("auto_tags", [])][:5],
            "intent_type": cls._validate_enum(
                result.get("intent_type"),
                ["reference", "tutorial", "inspiration", "deep-dive", "tool"],
                "reference"
            ),
            "technical_level": cls._validate_enum(
                result.get("technical_level"),
                ["beginner", "intermediate", "advanced", "general"],
                "general"
            ),
            "content_type": cls._validate_enum(
                result.get("content_type"),
                ["article", "documentation", "video", "tool", "paper", "other"],
                "article"
            ),
            "key_quotes": [str(q)[:300] for q in result.get("key_quotes", [])][:3],
            "suggested_folder": (
                result.get("suggested_folder") 
                if result.get("suggested_folder") in (folders or []) 
                else None
            ),
        }
        
        return validated

    @classmethod
    def _extract_queries_from_item(cls, item: Any) -> list[str]:
        """Extract web search query strings recursively from any Responses API item structure."""
        queries = []
        if not isinstance(item, dict):
            return queries

        item_type = item.get("type")

        # 1. Native web_search_call structure
        if item_type == "web_search_call":
            action = item.get("action", {})
            if isinstance(action, dict):
                q = action.get("query")
                if q:
                    queries.append(q)

        # 2. MCP tool call structure (from Responses API with remote MCP servers)
        elif item_type == "mcp_call":
            # MCP calls have: name, arguments, server_label
            args = item.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            if isinstance(args, dict):
                # Parallel Search MCP uses "search_queries" (array) and "objective" (string)
                search_queries = args.get("search_queries")
                objective = args.get("objective")
                q = args.get("query") or args.get("queries") or args.get("q")
                url = args.get("url")
                
                # Prefer objective as the human-readable label
                if objective:
                    queries.append(str(objective))
                elif search_queries and isinstance(search_queries, list):
                    queries.extend([str(x) for x in search_queries])
                elif q:
                    if isinstance(q, list):
                        queries.extend([str(x) for x in q])
                    else:
                        queries.append(str(q))
                elif url:
                    queries.append(f"Fetch: {url}")

        # 3. General tool_call or function_call at the top level
        elif item_type in ("tool_call", "function_call"):
            # Check name / tool_type
            name = item.get("name") or item.get("tool_name") or item.get("tool_type")
            if name in ("web_search", "parallel-search", "search", "web_fetch", "fetch"):
                args = item.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass
                if isinstance(args, dict):
                    q = args.get("query") or args.get("queries") or args.get("q")
                    url = args.get("url")
                    if q:
                        if isinstance(q, list):
                            queries.extend([str(x) for x in q])
                        else:
                            queries.append(str(q))
                    elif url:
                        queries.append(f"Fetch: {url}")

        # 4. Message items containing nested contents
        elif item_type == "message" and item.get("role") == "assistant":
            contents = item.get("content", [])
            for content_item in contents:
                if isinstance(content_item, dict):
                    content_type = content_item.get("type")
                    if content_type in ("tool_call", "function_call", "mcp_call"):
                        tc = content_item.get("tool_call") or content_item.get("function_call") or content_item
                        if isinstance(tc, dict):
                            name = tc.get("name") or tc.get("tool_name") or tc.get("tool_type")
                            if name in ("web_search", "parallel-search", "search", "web_fetch", "fetch"):
                                args = tc.get("arguments", {})
                                if isinstance(args, str):
                                    try:
                                        args = json.loads(args)
                                    except Exception:
                                        pass
                                if isinstance(args, dict):
                                    q = args.get("query") or args.get("queries") or args.get("q")
                                    url = args.get("url")
                                    if q:
                                        if isinstance(q, list):
                                            queries.extend([str(x) for x in q])
                                        else:
                                            queries.append(str(q))
                                    elif url:
                                        queries.append(f"Fetch: {url}")

        # 5. Fallback/Recursive traversal: search for any nested dicts or lists
        for k, v in item.items():
            if isinstance(v, dict):
                queries.extend(cls._extract_queries_from_item(v))
            elif isinstance(v, list):
                for elem in v:
                    if isinstance(elem, dict):
                        queries.extend(cls._extract_queries_from_item(elem))

        # Remove duplicates and preserve order
        unique_queries = []
        for query in queries:
            if query not in unique_queries:
                unique_queries.append(query)
        return unique_queries

    @classmethod
    def generate_research_with_search(cls, prompt: str, instructions: str) -> tuple[str, list[str]]:
        """Run web search research using the default (cheaper) model via Responses API.

        Falls back to a plain completions call (without search) if the Responses API
        is unavailable. Uses the default Azure OpenAI endpoint and deployment, not
        the Signal-specific overrides.
        """
        import requests

        endpoint = Config.AZURE_OPENAI_ENDPOINT
        api_key = Config.AZURE_OPENAI_API_KEY
        deployment = Config.AZURE_OPENAI_DEPLOYMENT_NAME

        if not endpoint or not api_key:
            logger.warning("Azure OpenAI endpoint or API key not configured. Falling back to standard Completions.")
            client = cls.get_chat_client()
            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content, []

        base_endpoint = endpoint.strip().rstrip("/")
        if not base_endpoint.endswith("/openai/v1"):
            if base_endpoint.endswith("/openai"):
                url = f"{base_endpoint}/v1/responses"
            else:
                url = f"{base_endpoint}/openai/v1/responses"
        else:
            url = f"{base_endpoint}/responses"

        headers = {
            "api-key": api_key,
            "Content-Type": "application/json"
        }

        # Configure the Parallel Search MCP tool definition
        mcp_tool = {
            "type": "mcp",
            "server_label": "parallel-search",
            "server_url": "https://search.parallel.ai/mcp",
            "require_approval": "never"
        }
        if Config.PARALLEL_API_KEY:
            mcp_tool["headers"] = {"Authorization": f"Bearer {Config.PARALLEL_API_KEY}"}

        data = {
            "model": deployment,
            "tools": [mcp_tool],
            "instructions": instructions,
            "input": prompt
        }

        try:
            logger.info("Calling Azure OpenAI Responses API for research with Parallel Search MCP...")
            res = requests.post(url, headers=headers, json=data, timeout=120)
            if res.status_code == 200:
                res_data = res.json()
                output_items = res_data.get("output", [])
                
                text = ""
                queries = []
                for item in output_items:
                    # Parse queries recursively
                    queries.extend(cls._extract_queries_from_item(item))
                    if item.get("type") == "message" and item.get("role") == "assistant":
                        contents = item.get("content", [])
                        for content_item in contents:
                            if content_item.get("type") == "output_text":
                                text = content_item.get("text", "")
                
                # Remove duplicates preserving order
                queries = list(dict.fromkeys(queries))
                
                if text:
                    logger.info("Responses API research successful. Extracted %d queries.", len(queries))
                    return text, queries
                else:
                    logger.warning("Responses API returned 200 but empty assistant text.")
            else:
                logger.warning("Responses API returned %d for research: %s", res.status_code, res.text[:500])
        except Exception as e:
            logger.warning("Responses API research call failed: %s", e)

        logger.info("Falling back to standard Chat Completions research generation...")
        client = cls.get_chat_client()
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content, []


    @classmethod
    def generate_brief_with_search(cls, prompt: str, instructions: str) -> str:
        """
        Generate Signal Daily Brief using Azure OpenAI's native Responses API with web search.
        
        Falls back to standard Chat Completions (without web search) if Responses API fails.
        """
        import requests
        
        endpoint = Config.SIGNAL_AZURE_OPENAI_ENDPOINT or Config.AZURE_OPENAI_ENDPOINT
        api_key = Config.SIGNAL_AZURE_OPENAI_API_KEY or Config.AZURE_OPENAI_API_KEY
        deployment = Config.SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME or Config.AZURE_OPENAI_DEPLOYMENT_NAME
        
        if not endpoint or not api_key:
            logger.warning("Azure OpenAI endpoint or API key not configured. Falling back to standard Completions.")
            return cls.generate_brief_completions_fallback(prompt, instructions, deployment)
            
        base_endpoint = endpoint.strip().rstrip("/")
        if not base_endpoint.endswith("/openai/v1"):
            if base_endpoint.endswith("/openai"):
                url = f"{base_endpoint}/v1/responses"
            else:
                url = f"{base_endpoint}/openai/v1/responses"
        else:
            url = f"{base_endpoint}/responses"
            
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "model": deployment,
            "tools": [{"type": "web_search"}],
            "instructions": instructions,
            "input": prompt
        }
        
        try:
            logger.info("Calling Azure OpenAI Responses API with web search...")
            res = requests.post(url, headers=headers, json=data, timeout=60)
            if res.status_code == 200:
                res_data = res.json()
                output_items = res_data.get("output", [])
                text = ""
                # Find the assistant's output message
                for item in output_items:
                    if item.get("type") == "message" and item.get("role") == "assistant":
                        contents = item.get("content", [])
                        for content_item in contents:
                            if content_item.get("type") == "output_text":
                                text = content_item.get("text", "")
                                break
                if text:
                    logger.info("Responses API brief generation successful.")
                    return text
                else:
                    logger.warning("Responses API returned successful code but empty assistant text.")
            else:
                logger.warning(f"Responses API returned non-200 code: {res.status_code}. Response: {res.text}")
        except Exception as e:
            logger.warning(f"Responses API call failed with exception: {e}")
            
        logger.info("Falling back to standard Chat Completions daily brief generation...")
        return cls.generate_brief_completions_fallback(prompt, instructions, deployment)

    @classmethod
    def generate_signal_title(cls, brief_content: str) -> str | None:
        """Generate a single, sharp title for a finished Signal brief.

        Runs as a small, cheap dedicated pass over the synthesized memo so title
        quality does not depend on how the long synthesis completion "warms up".
        Uses the nano deployment when configured, falling back to the default
        chat deployment. Returns None on any failure so the caller can fall back
        to the title parsed from the brief's first line.
        """
        if not brief_content or not brief_content.strip():
            return None

        # Title only needs the substance of the brief, not the whole thing.
        excerpt = brief_content.strip()[:6000]

        deployment_name = (
            Config.AZURE_OPENAI_NANO_DEPLOYMENT_NAME
            or Config.AZURE_OPENAI_DEPLOYMENT_NAME
        )

        prompt = (
            "Below is a daily intelligence brief. Write a single title for it.\n\n"
            "Requirements:\n"
            "- One line, no quotes, no markdown, no trailing punctuation.\n"
            "- Maximum 14 words. Concrete and specific to this brief's main thread.\n"
            "- Capture the most important development or throughline, not a generic label.\n"
            "- Sound like a sharp analyst's headline, not clickbait. No em dashes.\n\n"
            "Brief:\n"
            '"""\n'
            f"{excerpt}\n"
            '"""\n\n'
            "Return only the title text."
        )

        try:
            client = cls.get_chat_client()
            response = client.chat.completions.create(
                model=deployment_name,
                messages=[
                    {"role": "system", "content": "You write concise, specific titles. Respond with only the title text."},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=10000,
            )
            title = (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("Dedicated title generation failed: %s", exc)
            return None

        if not title:
            return None
        # Defensive cleanup: collapse to first line, strip wrapping quotes/markdown.
        title = title.splitlines()[0].strip()
        title = title.strip("#").strip()
        title = title.strip('"\u201c\u201d\u2018\u2019').strip()
        title = title.strip("*_").strip()
        return title or None

    @classmethod
    def generate_brief_with_verbosity(cls, prompt: str, instructions: str, verbosity: str = "high") -> str:
        """
        Generate Signal Daily Brief using Azure OpenAI's native Responses API with the specified verbosity.
        No tools are passed since this is a pure synthesis step.
        Falls back to standard Chat Completions if Responses API fails.
        """
        import requests
        
        endpoint = Config.SIGNAL_AZURE_OPENAI_ENDPOINT or Config.AZURE_OPENAI_ENDPOINT
        api_key = Config.SIGNAL_AZURE_OPENAI_API_KEY or Config.AZURE_OPENAI_API_KEY
        deployment = Config.SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME or Config.AZURE_OPENAI_DEPLOYMENT_NAME
        
        if not endpoint or not api_key:
            logger.warning("Azure OpenAI endpoint or API key not configured. Falling back to standard Completions.")
            return cls.generate_brief_completions_fallback(prompt, instructions, deployment)
            
        base_endpoint = endpoint.strip().rstrip("/")
        if not base_endpoint.endswith("/openai/v1"):
            if base_endpoint.endswith("/openai"):
                url = f"{base_endpoint}/v1/responses"
            else:
                url = f"{base_endpoint}/openai/v1/responses"
        else:
            url = f"{base_endpoint}/responses"
            
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "model": deployment,
            "instructions": instructions,
            "input": prompt,
            "text": {
                "verbosity": verbosity
            }
        }
        
        try:
            logger.info("Calling Azure OpenAI Responses API with verbosity %s...", verbosity)
            res = requests.post(url, headers=headers, json=data, timeout=120)
            
            # If "high" verbosity is unsupported, retry with "medium"
            if res.status_code == 400 and verbosity == "high":
                try:
                    err_json = res.json()
                    err_msg = err_json.get("error", {}).get("message", "")
                    if "verbosity" in err_msg or "unsupported_value" in err_json.get("error", {}).get("code", ""):
                        logger.warning("Verbosity 'high' unsupported by model. Retrying with 'medium'...")
                        data["text"]["verbosity"] = "medium"
                        verbosity = "medium"
                        res = requests.post(url, headers=headers, json=data, timeout=120)
                except Exception as parse_exc:
                    logger.debug("Failed to parse 400 error JSON or retry: %s", parse_exc)

            if res.status_code == 200:
                res_data = res.json()
                output_items = res_data.get("output", [])
                text = ""
                # Find the assistant's output message
                for item in output_items:
                    if item.get("type") == "message" and item.get("role") == "assistant":
                        contents = item.get("content", [])
                        for content_item in contents:
                            if content_item.get("type") == "output_text":
                                text = content_item.get("text", "")
                                break
                if text:
                    logger.info("Responses API brief generation successful with verbosity %s.", verbosity)
                    return text
                else:
                    logger.warning("Responses API returned successful code but empty assistant text.")
            else:
                logger.warning(f"Responses API returned non-200 code: {res.status_code}. Response: {res.text}")
        except Exception as e:
            logger.warning(f"Responses API call failed with exception: {e}")
            
        logger.info("Falling back to standard Chat Completions daily brief generation...")
        return cls.generate_brief_completions_fallback(prompt, instructions, deployment)

    @classmethod
    def generate_brief_completions_fallback(cls, prompt: str, instructions: str, deployment: str) -> str:
        """Fallback chat completions implementation without search."""
        client, model = cls.get_signal_chat_client_and_model()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    
    @staticmethod
    def _validate_enum(value: str, allowed: list[str], default: str) -> str:
        """Validate that a value is in the allowed list."""
        if value and value.lower() in allowed:
            return value.lower()
        return default
