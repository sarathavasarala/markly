"""Content extraction service."""
import re
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from typing import Optional

from config import Config


class ContentExtractor:
    """Extract content from URLs."""
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    TIMEOUT = 15
    
    @classmethod
    def extract(cls, url: str) -> dict:
        """
        Extract content from a URL.
        
        Returns dict with:
        - title: page title
        - description: meta description
        - content: main text content
        - favicon_url: favicon URL
        - thumbnail_url: og:image or similar
        - domain: domain name
        """
        result = {
            "title": None,
            "description": None,
            "content": None,
            "favicon_url": None,
            "thumbnail_url": None,
            "domain": None,
        }
        
        # Parse domain
        try:
            parsed = urlparse(url)
            result["domain"] = parsed.netloc.replace("www.", "")
        except Exception:
            pass
        
        # Try Jina Reader API first if available
        if Config.JINA_READER_API_KEY:
            jina_result = cls._extract_via_jina(url)
            if jina_result.get("content"):
                result.update(jina_result)
                return result
        
        # Fallback to BeautifulSoup
        bs_result = cls._extract_via_beautifulsoup(url)
        result.update(bs_result)
        
        return result
    
    @classmethod
    def _extract_via_jina(cls, url: str) -> dict:
        """Extract content using Jina Reader API."""
        import urllib.parse
        try:
            # Properly encode the URL to handle special characters
            encoded_url = urllib.parse.quote(url, safe='')
            jina_url = f"https://r.jina.ai/{encoded_url}"
            headers = {
                "Authorization": f"Bearer {Config.JINA_READER_API_KEY}",
                "Accept": "application/json",
            }
            
            print(f"Calling Jina Reader for: {url}")
            response = requests.get(jina_url, headers=headers, timeout=cls.TIMEOUT)
            response.raise_for_status()
            
            raw_data = response.json()
            
            # Jina API returns content nested inside a 'data' object
            data = raw_data.get("data", {}) if "data" in raw_data else raw_data
            
            title = data.get("title")
            description = data.get("description")
            content = data.get("content", "")
            
            if not content and not title:
                print(f"Jina returned empty data for {url}")
                return {}

            return {
                "title": title,
                "description": description,
                "content": content[:15000],  # Limit content size
            }
            
        except Exception as e:
            print(f"Jina extraction failed for {url}: {str(e)}")
            return {}
    
    @classmethod
    def _extract_via_beautifulsoup(cls, url: str) -> dict:
        """Extract content using BeautifulSoup."""
        result = {}
        
        try:
            response = requests.get(url, headers=cls.HEADERS, timeout=cls.TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "lxml")
            
            # Extract title
            if soup.title:
                result["title"] = soup.title.string.strip() if soup.title.string else None
            
            # Extract meta description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                result["description"] = meta_desc.get("content", "")
            
            # Extract Open Graph data
            og_title = soup.find("meta", property="og:title")
            if og_title and not result.get("title"):
                result["title"] = og_title.get("content")
            
            og_desc = soup.find("meta", property="og:description")
            if og_desc and not result.get("description"):
                result["description"] = og_desc.get("content")
            
            og_image = soup.find("meta", property="og:image")
            if og_image:
                result["thumbnail_url"] = og_image.get("content")
            
            # Extract favicon
            favicon = soup.find("link", rel=lambda x: x and "icon" in x.lower() if x else False)
            if favicon:
                favicon_href = favicon.get("href", "")
                if favicon_href.startswith("http"):
                    result["favicon_url"] = favicon_href
                elif favicon_href.startswith("/"):
                    parsed = urlparse(url)
                    result["favicon_url"] = f"{parsed.scheme}://{parsed.netloc}{favicon_href}"
            
            # If no favicon found, try default location
            if not result.get("favicon_url"):
                parsed = urlparse(url)
                result["favicon_url"] = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
            
            # Extract main content
            content = cls._extract_main_content(soup)
            result["content"] = content[:15000] if content else None  # Limit size
            
        except Exception as e:
            print(f"BeautifulSoup extraction failed for {url}: {e}")
        
        return result
    
    @classmethod
    def _extract_main_content(cls, soup: BeautifulSoup) -> Optional[str]:
        """Extract the main text content from a page."""
        # Remove script, style, nav, footer, header elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        
        # Try to find main content area
        main_content = None
        
        # Common main content selectors
        selectors = [
            "article",
            "main",
            '[role="main"]',
            ".post-content",
            ".article-content",
            ".entry-content",
            ".content",
            "#content",
        ]
        
        for selector in selectors:
            found = soup.select_one(selector)
            if found:
                main_content = found
                break
        
        # Fallback to body
        if not main_content:
            main_content = soup.body
        
        if not main_content:
            return None
        
        # Get text and clean up
        text = main_content.get_text(separator="\n", strip=True)
        
        # Clean up excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        
        return text.strip()
