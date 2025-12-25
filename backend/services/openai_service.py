"""Azure OpenAI service for LLM and embeddings."""
import json
from typing import Optional
from openai import OpenAI, AzureOpenAI

from config import Config


class AzureOpenAIService:
    """Service for Azure OpenAI operations."""
    
    _chat_client: Optional[AzureOpenAI] = None
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
    def enrich_bookmark(cls, url: str, title: str, content: str, user_notes: str = None) -> dict:
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
        
        # Truncate content if too long
        if content and len(content) > 10000:
            content = content[:10000] + "..."
        
        prompt = f"""Analyze this bookmarked article and provide structured metadata.

URL: {url}
Title: {title or 'Unknown'}
Content: {content or 'No content extracted'}
User Notes: {user_notes or 'None provided'}

Return a JSON object with exactly these fields:
- clean_title: A clean, concise title (max 60 characters). If the original title is good, keep it.
- ai_summary: A 2-sentence summary of the content. Be concise and informative.
- auto_tags: An array of 3-5 relevant tags (lowercase, no spaces, use hyphens). Include technology names, concepts, and topics.
- intent_type: One of: "reference", "tutorial", "inspiration", "deep-dive", "tool"
- technical_level: One of: "beginner", "intermediate", "advanced", "general"
- content_type: One of: "article", "documentation", "video", "tool", "paper", "other"
- key_quotes: An array of 0-3 notable quotes from the content (short, impactful quotes only)

Return ONLY valid JSON, no markdown formatting or explanation."""

        response = client.chat.completions.create(
            model=Config.AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that analyzes web content and provides structured metadata. Always respond with valid JSON only."
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
            }
        
        # Validate and sanitize the result
        validated = {
            "clean_title": str(result.get("clean_title", title or "Untitled"))[:60],
            "ai_summary": str(result.get("ai_summary", ""))[:500],
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
        }
        
        return validated
    
    @classmethod
    def generate_collection_proposals(cls, bookmarks: list[dict]) -> list[dict]:
        """
        Analyze bookmarks and propose collections.
        
        Returns list of collection proposals with bookmark IDs.
        """
        client = cls.get_chat_client()
        
        # Prepare bookmark summaries for the prompt
        bookmark_summaries = []
        for b in bookmarks[:100]:  # Limit to 100 bookmarks for prompt size
            summary = {
                "id": b["id"],
                "title": b.get("clean_title") or b.get("original_title", "Untitled"),
                "domain": b.get("domain", ""),
                "tags": b.get("auto_tags", []),
                "content_type": b.get("content_type", ""),
                "summary": b.get("ai_summary", "")[:100],
            }
            bookmark_summaries.append(summary)
        
        prompt = f"""Analyze these bookmarks and propose logical collections to organize them.

Bookmarks:
{json.dumps(bookmark_summaries, indent=2)}

Return a JSON object with a "collections" array. Each collection should have:
- name: A descriptive collection name (2-4 words)
- description: Why these bookmarks belong together (1 sentence)
- suggested_icon: A single emoji that represents the collection
- bookmark_ids: Array of bookmark IDs that belong in this collection
- rationale: Brief explanation of the grouping logic

Guidelines:
- Aim for 5-10 collections
- Each bookmark can appear in multiple collections
- Group by topic, technology, purpose, or content type
- Make collections useful for navigation and discovery

Return ONLY valid JSON, no markdown formatting."""

        response = client.chat.completions.create(
            model=Config.AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that organizes bookmarks into meaningful collections. Always respond with valid JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=2000,
            response_format={"type": "json_object"},
        )
        
        result_text = response.choices[0].message.content
        
        try:
            result = json.loads(result_text)
            collections = result.get("collections", [])
        except json.JSONDecodeError:
            collections = []
        
        return collections
    
    @classmethod
    def generate_resurface_suggestions(
        cls, 
        recent_bookmarks: list[dict], 
        old_bookmarks: list[dict]
    ) -> list[dict]:
        """
        Suggest old bookmarks that might be relevant based on recent activity.
        
        Returns list of bookmark IDs with reasons.
        """
        client = cls.get_chat_client()
        
        recent_summaries = [
            {
                "title": b.get("clean_title", ""),
                "tags": b.get("auto_tags", []),
                "summary": b.get("ai_summary", "")[:100],
            }
            for b in recent_bookmarks[:10]
        ]
        
        old_summaries = [
            {
                "id": b["id"],
                "title": b.get("clean_title", ""),
                "tags": b.get("auto_tags", []),
                "summary": b.get("ai_summary", "")[:100],
            }
            for b in old_bookmarks[:50]
        ]
        
        prompt = f"""Based on the user's recent bookmarks, suggest older bookmarks they might want to revisit.

Recent Bookmarks:
{json.dumps(recent_summaries, indent=2)}

Older Bookmarks to Consider:
{json.dumps(old_summaries, indent=2)}

Return a JSON object with a "suggestions" array. Each suggestion should have:
- bookmark_id: The ID of the old bookmark to resurface
- reason: A brief explanation of why this is relevant (1 sentence)

Select 3-5 old bookmarks that relate to the recent topics or could be helpful given the user's current interests.

Return ONLY valid JSON, no markdown formatting."""

        response = client.chat.completions.create(
            model=Config.AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that identifies relevant past bookmarks. Always respond with valid JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=500,
            response_format={"type": "json_object"},
        )
        
        result_text = response.choices[0].message.content
        
        try:
            result = json.loads(result_text)
            suggestions = result.get("suggestions", [])
        except json.JSONDecodeError:
            suggestions = []
        
        return suggestions
    
    @staticmethod
    def _validate_enum(value: str, allowed: list[str], default: str) -> str:
        """Validate that a value is in the allowed list."""
        if value and value.lower() in allowed:
            return value.lower()
        return default
