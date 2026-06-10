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
        - content_format: "markdown" | "text" | None
        - favicon_url: favicon URL
        - thumbnail_url: og:image or similar
        - domain: domain name
        """
        import concurrent.futures
        
        result = {
            "title": None,
            "description": None,
            "content": None,
            "content_format": None,
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
        
        jina_res = {}
        # 1. Try Jina Reader API first if configured
        if Config.JINA_READER_API_KEY:
            try:
                jina_res = cls._extract_via_jina(url)
            except Exception as e:
                print(f"Jina extraction failed: {e}")
                
        # If Jina succeeded and extracted content, we skip BeautifulSoup fallback
        if jina_res.get("content"):
            for key, val in jina_res.items():
                if val:
                    result[key] = val
        else:
            # 2. Try BeautifulSoup / Newspaper if Jina failed or is not configured
            bs_res = {}
            try:
                bs_res = cls._extract_via_beautifulsoup(url)
            except Exception as e:
                print(f"BeautifulSoup extraction failed: {e}")
                
            # Merge BeautifulSoup results
            for key, val in bs_res.items():
                if val:
                    result[key] = val
                    
            # Merge Jina metadata if any was retrieved (even if content failed)
            for key, val in jina_res.items():
                if val and not result.get(key):
                    result[key] = val

        # Final fallback for favicon if still missing
        if not result.get("favicon_url") and result.get("domain"):
            result["favicon_url"] = f"https://www.google.com/s2/favicons?domain={result['domain']}&sz=64"
        
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
            
            response = requests.get(jina_url, headers=headers, timeout=cls.TIMEOUT)
            response.raise_for_status()
            
            raw_data = response.json()
            
            # Jina API returns content nested inside a 'data' object
            data = raw_data.get("data", {}) if "data" in raw_data else raw_data
            
            content = data.get("content", "")
            return {
                "title": data.get("title"),
                "description": data.get("description"),
                "content": content[:Config.ARCHIVE_MAX_CHARS] if content else None,
                "content_format": "markdown" if content else None,
            }
            
        except Exception as e:
            print(f"Jina extraction failed for {url}: {str(e)}")
            return {}
    
    @classmethod
    def _extract_via_beautifulsoup(cls, url: str) -> dict:
        """Extract content using BeautifulSoup and newspaper3k."""
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
            result["favicon_url"] = cls.extract_favicon(url, soup)
            
            # Try newspaper3k extraction
            newspaper_content = None
            try:
                from newspaper import Article
                article = Article(url)
                article.set_html(response.text)
                article.parse()
                if article.text and article.text.strip():
                    newspaper_content = article.text.strip()
            except Exception as e:
                print(f"Newspaper3k parse failed: {e}")
            
            if newspaper_content:
                result["content"] = newspaper_content[:Config.ARCHIVE_MAX_CHARS]
                result["content_format"] = "text"
            else:
                # Fallback to BeautifulSoup selector extraction
                content = cls._extract_main_content(soup)
                if content:
                    result["content"] = content[:Config.ARCHIVE_MAX_CHARS]
                    result["content_format"] = "text"
            
        except Exception as e:
            print(f"BeautifulSoup extraction failed for {url}: {e}")
        
        return result

    @classmethod
    def extract_favicon(cls, url: str, soup: Optional[BeautifulSoup] = None) -> Optional[str]:
        """Discovery of favicon with multiple fallbacks."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            
            if soup:
                favicon = soup.find("link", rel=lambda x: x and "icon" in x.lower() if x else False)
                if favicon:
                    href = favicon.get("href", "")
                    if href.startswith("http"):
                        return href
                    if href.startswith("//"):
                        return f"{parsed.scheme}:{href}"
                    if href.startswith("/"):
                        return f"{parsed.scheme}://{parsed.netloc}{href}"
                    # Relative path
                    return f"{parsed.scheme}://{parsed.netloc}/{href.lstrip('/')}"

            # Try default /favicon.ico location check is slow, so we jump to Google API
            # which is very reliable and fast for many sites
            return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        except Exception:
            return None
    
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
