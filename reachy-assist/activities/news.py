"""Daily news reader — fetches top headlines and reads them aloud."""

import json
import urllib.request
import re


def fetch_headlines(count: int = 5) -> list[dict]:
    """Fetch top headlines from Google News RSS via a simple parser."""
    try:
        url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={"User-Agent": "reachy-assist/1.0"})
        resp = urllib.request.urlopen(req, timeout=8)
        xml = resp.read().decode("utf-8")
        # Simple XML parse for <item><title>...</title></item>
        items = re.findall(r"<item>.*?<title>(.*?)</title>.*?</item>", xml, re.DOTALL)
        headlines = []
        for item in items[:count]:
            # Clean HTML entities
            title = item.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            title = title.replace("&quot;", '"').replace("&#39;", "'")
            # Remove source suffix like " - CNN"
            title = re.sub(r"\s*-\s*[A-Za-z\s]+$", "", title)
            headlines.append({"title": title.strip()})
        return headlines
    except Exception as e:
        return [{"title": f"Could not fetch news: {e}"}]


def news_briefing(count: int = 5) -> str:
    """Return a spoken news briefing."""
    headlines = fetch_headlines(count)
    if not headlines:
        return "I couldn't get the news right now. Try again later."
    lines = ["Here are today's top headlines:"]
    for i, h in enumerate(headlines, 1):
        lines.append(f"{i}. {h['title']}")
    lines.append("\nWould you like to hear more about any of these?")
    return "\n".join(lines)

def headline_count() -> int:
    headlines = fetch_headlines()
    return len(headlines)

