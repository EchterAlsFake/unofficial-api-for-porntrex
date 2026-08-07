import re

from typing import Any
from selectolax.lexbor import LexborHTMLParser



PATTERN_URL_KEY = re.compile(r"^video_(?:alt_)?url(?:\d+)?$", re.I)       # video_url, video_alt_url, video_alt_url2, ...
PATTERN_RESOLUTION_TEXT = re.compile(r"(\d{3,4})p", re.I)                 # "480p", "1080p FHD", "2160p 4K"
PATTERN_RESOLUTION_IN_URL = re.compile(r"_(\d{3,4})p\.mp4/?$", re.I)      # "..._720p.mp4" or "..._2160p.mp4"
PATTERN_MP4 = re.compile(r"\.mp4/?$", re.I)


def extractor_html(content: str) -> list[dict[str, Any]]:
    parser = LexborHTMLParser(content)
    extracted_videos = []

    # Target the main container for the video items
    containers = parser.css("div.video-preview-screen.video-item.thumb-item")

    for container in containers:
        # Initialize a dictionary mapping to your Video dataclass fields
        video_data = {}

        # 1. URL
        a_tag = container.css_first("a.thumb")
        video_data["url"] = a_tag.attributes.get("href") if a_tag else None

        # 2. Video ID
        video_data["video_id"] = container.attributes.get("data-item-id")

        # 3. Title & 4. Thumbnail
        img_tag = container.css_first("img.cover")
        if img_tag:
            video_data["title"] = img_tag.attributes.get("alt")
            video_data["thumbnail"] = img_tag.attributes.get("data-src")

        # 5. Qualities (Stored as a list)
        quality_tag = container.css_first("span.quality")
        if quality_tag:
            video_data["video_qualities"] = [quality_tag.text(strip=True)]

        # 6. Views
        views_tag = container.css_first("div.viewsthumb")
        if views_tag:
            video_data["views"] = views_tag.text(strip=True)

        # 7. Duration
        duration_tag = container.css_first("div.durations")
        if duration_tag:
            video_data["duration"] = duration_tag.text(strip=True)

        # 8. Publish Date
        date_tag = container.css_first("ul.list-unstyled li")
        if date_tag:
            video_data["publish_date"] = date_tag.text(strip=True)

        if video_data.get("url"):
            extracted_videos.append(video_data)

    return extracted_videos
