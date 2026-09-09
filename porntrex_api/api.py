from __future__ import annotations

import copy
import os
import re
import json5
import asyncio
import logging

from typing import AsyncGenerator, ClassVar
from dataclasses import dataclass
from selectolax.lexbor import LexborHTMLParser
from base_api.modules.config import IteratorConfig
from base_api import (
    BaseCore,
    BaseMedia,
    DownloadConfigRAW,
    ErrorAction,
    ErrorMode,
    Helper,
    MediaLoadError,
    MediaLoadErrors,
    RetryPolicy,
    ScrapeErrorContext,
    ScrapeResult,
    media_field,
    make_iterator_config,
    is_resource_gone,
    default_on_error,
    scrape_stream,
)
import argparse

from base_api.modules.logger import configure_app_logging
from base_api.modules.static_functions import choose_quality_from_list, normalize_quality_value, str_to_bool
from base_api.modules.errors import (
    DownloadCancelled,
    BotProtectionDetected,
    HTTPStatusError,
    InvalidProxy,
    NetworkRequestError,
    ResourceGone,
    UnknownError,
)

from porntrex_api.modules.errors import (NetworkError, NotFound, UnknownNetworkError, BotDetection, ProxyError,
                                         DownloadFailed)
from porntrex_api.modules.consts import (PATTERN_MP4, PATTERN_URL_KEY, PATTERN_RESOLUTION_IN_URL,
                                         PATTERN_RESOLUTION_TEXT, extractor_html)


logger = logging.getLogger("Porntrex API")
logger.addHandler(logging.NullHandler())

_contains_resource_gone = is_resource_gone
on_error = default_on_error



async def get_html_content(core: BaseCore, url: str) -> str:
    try:
        return await core.fetch_text(url)

    except HTTPStatusError as e:
        logger.exception("Request failed for %s: %s", url, e)
        if e.status_code == 404:
            raise NotFound(f"Server returned 404 for: {url}") from e
        raise NetworkError(f"Request failed for {url}: {e}") from e

    except NetworkRequestError as e:
        logger.exception("Request failed for %s: %s", url, e)
        raise NetworkError(f"Request failed for {url}: {e}") from e

    except InvalidProxy as e:
        logger.exception("Request failed for %s: %s", url, e)
        raise ProxyError(f"Request failed for {url}: {e}") from e

    except BotProtectionDetected as e:
        logger.exception("Request failed for %s: %s", url, e)
        raise BotDetection(f"Request failed for {url}: {e}") from e

    except UnknownError as e:
        logger.exception("Request failed for %s: %s", url, e)
        raise UnknownNetworkError(f"Request failed for {url}: {e}") from e

    except Exception:
        logger.exception("Failed to fetch or decode response for %s", url)
        raise


@dataclass(kw_only=True, slots=True)
class Video(BaseMedia):
    url: str
    core: BaseCore
    title: str | None = media_field("html")
    video_id: str | None = media_field("html")
    categories: list[str] | None = media_field("html")
    tags: list[str] | None = media_field("html")
    license_code: str | None = media_field("html")
    lrc: str | None = media_field("html")
    rnd: str | None = media_field("html")
    author: str | None = media_field("html")
    publish_date: str | None = media_field("html")
    views: str | None = media_field("html")
    duration: str | None = media_field("html")
    description: str | None = media_field("html")
    subscribers_count: str | None = media_field("html")
    thumbnail: str | None = media_field("html")
    direct_download_urls: list[str] | None = media_field("html")
    video_qualities: list[str] | None = media_field("html")

    loader_methods: ClassVar[dict[str, str]] = {"html": "_load_html"}

    async def _load_html(self) -> dict[str, object]:
        html_content = await get_html_content(core=self.core, url=self.url)
        return await asyncio.to_thread(self._extract_data, html_content)

    def _extract_data(self, html_content: str) -> dict:
        parser = LexborHTMLParser(html_content)

        # Layout anchors: 'div.video-info' and 'div.block-video' are expected on all video pages
        if not parser.css_first("div.video-info") and not parser.css_first("div.block-video"):
            logger.warning(
                "Video container anchor ('div.video-info' / 'div.block-video') not found for %s; page layout may have changed.",
                self.url,
            )

        json_data: dict = {}
        m = re.search(r"var\s+flashvars\s*=\s*({.*?})\s*;", html_content, re.S)
        if m:
            try:
                json_data = json5.loads(m.group(1))
            except Exception as e:
                logger.warning("Failed to parse flashvars JSON for %s: %s", self.url, e)
        else:
            logger.warning("flashvars script block not found for %s; layout may have changed.", self.url)

        # Title: flashvars -> HTML p.title-video
        title = json_data.get("video_title")
        if not title:
            title_node = parser.css_first("p.title-video")
            title = title_node.text(strip=True) if title_node else None
        if not title:
            logger.warning("Title not found for %s", self.url)

        # Video ID: flashvars -> HTML input[name="video_id"] -> URL regex
        video_id = json_data.get("video_id")
        if not video_id:
            vid_node = parser.css_first("input[name='video_id']")
            if vid_node:
                video_id = vid_node.attributes.get("value")
            elif m_id := re.search(r"/video/(\d+)", self.url):
                video_id = m_id.group(1)
        if not video_id:
            logger.warning("Video ID not found for %s", self.url)

        # Categories: flashvars -> HTML .js-categories
        if raw_cats := json_data.get("video_categories"):
            categories = [c.strip() for c in raw_cats.split(",") if c.strip()]
        else:
            categories = [
                a.text(strip=True)
                for a in parser.css("div.js-categories a.js-cat")
                if a.text(strip=True)
            ]
        if not categories:
            logger.warning("Categories not found for %s", self.url)

        # Tags: flashvars -> HTML tag links
        if raw_tags := json_data.get("video_tags"):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        else:
            tags = [
                a.text(strip=True)
                for a in parser.css("div.items-holder a[href*='/tags/']")
                if a.text(strip=True)
            ]
        if not tags:
            logger.warning("Tags not found for %s", self.url)

        license_code = json_data.get("license_code")
        lrc = json_data.get("lrc")
        rnd = json_data.get("rnd")

        # Author: div.username a -> div.username
        author_node = parser.css_first("div.username a") or parser.css_first("div.username")
        author = author_node.text(strip=True) if author_node else None
        if not author:
            logger.warning("Author not found for %s", self.url)

        # Metadata items (publish_date, views, duration): div.info-block div.item em
        ems = parser.css("div.info-block div.item em") or parser.css("div.video-info div.item em")
        publish_date = ems[0].text(strip=True) if len(ems) > 0 else None
        views = ems[1].text(strip=True) if len(ems) > 1 else None
        duration = ems[2].text(strip=True) if len(ems) > 2 else None
        if not ems:
            logger.warning("Metadata items (publish_date, views, duration) not found for %s", self.url)

        # Description: em.des-link -> div.videodesc
        desc_node = parser.css_first("em.des-link") or parser.css_first("div.videodesc .items-holder")
        description = desc_node.text(strip=True) if desc_node else None
        if not description:
            logger.warning("Description not found for %s", self.url)

        # Subscribers count: div.button-infow
        sub_node = parser.css_first("div.button-infow")
        subscribers_count = sub_node.text(strip=True) if sub_node else None
        if not subscribers_count:
            logger.warning("Subscribers count not found for %s", self.url)

        # Thumbnail: flashvars preview_url -> poster/player img
        image = json_data.get("preview_url")
        if not image:
            img_node = parser.css_first("div.fp-poster img") or parser.css_first("div.premium-player img")
            if img_node:
                image = img_node.attributes.get("src") or img_node.attributes.get("data-src")

        if image:
            thumbnail = f"https:{image}" if image.startswith("//") else image
        else:
            thumbnail = None
            logger.warning("Thumbnail not found for %s", self.url)

        pairs = self._collect_height_url_pairs(json_data)
        video_qualities = [str(h) for h, _ in pairs]
        direct_download_urls = [url for _, url in pairs]
        if not direct_download_urls:
            logger.warning("Direct download URLs not found for %s", self.url)

        return {
            "title": title,
            "video_id": video_id,
            "categories": categories,
            "tags": tags,
            "license_code": license_code,
            "lrc": lrc,
            "rnd": rnd,
            "author": author,
            "publish_date": publish_date,
            "views": views,
            "duration": duration,
            "description": description,
            "subscribers_count": subscribers_count,
            "thumbnail": thumbnail,
            "direct_download_urls": direct_download_urls,
            "video_qualities": video_qualities,
        }

    @staticmethod
    def _extract_height_for_key(key: str, url: str, json_data: dict) -> int | None:
        """
        Try to get the numeric height from "<key>_text" first, then from the URL pattern.
        """
        # 1) From "<key>_text" if present (e.g., "720p HD", "480p")
        label = json_data.get(f"{key}_text")
        if label:
            m = PATTERN_RESOLUTION_TEXT.search(str(label))
            if m:
                return int(m.group(1))

        # 2) From the URL itself if it ends with "..._720p.mp4"
        m = PATTERN_RESOLUTION_IN_URL.search(url)
        if m:
            return int(m.group(1))

        return None

    @classmethod
    def _collect_height_url_pairs(cls, json_data: dict) -> list[tuple[int, str]]:
        """
        Build (height, url) pairs from the JSON payload.
        Only keeps valid .mp4 URLs that have a resolvable height.
        Deduplicates by height (last one wins if duplicates found).
        """
        by_height: dict[int, str] = {}
        for k, v in json_data.items():
            if not isinstance(v, str):
                continue
            if not PATTERN_URL_KEY.match(k):
                continue
            if not PATTERN_MP4.search(v):
                continue

            h = cls._extract_height_for_key(k, v, json_data)
            if h is not None:
                by_height[h] = f"https:{v}" if v.startswith("//") else v

        # Sort by ascending height
        return sorted(by_height.items(), key=lambda kv: kv[0])

    @classmethod
    def get_video_qualities(cls, json_data: dict) -> list[str]:
        """
        :return: (list[str]) available qualities as e.g. ["480", "720", "1080", "2160"]
        """
        return [str(h) for h, _ in cls._collect_height_url_pairs(json_data)]

    @classmethod
    def get_direct_download_urls(cls, json_data: dict) -> list[str]:
        """
        :return: (list[str]) direct MP4 URLs aligned in ascending order of quality.
                 Ordering matches the sorted `video_qualities`.
        """
        return [url for _, url in cls._collect_height_url_pairs(json_data)]

    async def download(self, configuration: DownloadConfigRAW) -> bool:
        try:
            await self.load_fields("direct_download_urls", "video_qualities", "title")
            config = copy.deepcopy(configuration)
            cdn_urls = self.direct_download_urls or []
            quals = self.video_qualities or []

            if not cdn_urls or not quals:
                logger.error("No download URLs or qualities available for %s", self.url)
                raise DownloadFailed(f"No download URLs available for {self.url}")

            qn = normalize_quality_value(config.quality)
            chosen_height = choose_quality_from_list(quals, qn)

            quality_url_map = {int(q): url for q, url in zip(quals, cdn_urls)}
            download_url = quality_url_map.get(chosen_height)
            if not download_url:
                logger.error("Chosen quality %s not found in available URLs for %s", chosen_height, self.url)
                raise DownloadFailed(f"Quality {chosen_height} not found for {self.url}")

            if not config.no_title:
                safe_title = f"{self.title}.mp4"
                config.path = os.path.join(config.path, safe_title)

            await self.core.legacy_download(url=download_url, configuration=config)
            return True
        except DownloadCancelled:
            raise
        except Exception as e:
            logger.exception("Download failed for %s: %s", self.url, e)
            raise DownloadFailed(f"Download failed for {self.url}: {e}") from e


@dataclass(kw_only=True, slots=True)
class ChannelModelHelper(BaseMedia):
    url: str
    core: BaseCore
    name: str | None = media_field("html")
    information: dict | None = media_field("html")
    thumbnail: str | None = media_field("html")

    loader_methods: ClassVar[dict[str, str]] = {"html": "_load_html"}

    async def _load_html(self) -> dict[str, object]:
        html_content = await get_html_content(core=self.core, url=self.url)
        return await asyncio.to_thread(self._extract_html, html_content)

    def _extract_html(self, html_content: str) -> dict:
        parser = LexborHTMLParser(html_content)

        # Layout anchors: 'div.profile-model' and 'div.sidebar' are expected on channel/model pages
        if not parser.css_first("div.profile-model") and not parser.css_first("div.sidebar"):
            logger.warning(
                "Channel/Model container anchor ('div.profile-model' / 'div.sidebar') not found for %s; page layout may have changed.",
                self.url,
            )

        # Name: div.name a -> div.name h1 -> h1
        name_node = parser.css_first("div.name a") or parser.css_first("div.name h1") or parser.css_first("h1")
        name = name_node.text(strip=True) if name_node else None
        if not name:
            logger.warning("Channel/Model name not found for %s", self.url)

        # Information: div.sidebar div.info -> div.info
        information = {}
        info_container = parser.css_first("div.sidebar div.info") or parser.css_first("div.info")
        if info_container:
            for p in info_container.css("p"):
                text = p.text().strip()
                if ":" not in text:
                    continue
                parts = text.split(":", 1)
                k = " ".join(parts[0].split())
                v = " ".join(parts[1].split()) if "\n" in parts[1] else parts[1].strip()
                if k and v:
                    information[k] = v
        else:
            logger.warning("Information container ('div.sidebar div.info') not found for %s", self.url)

        # Thumbnail: div.profile-model-info img -> div.profile-model img
        img_node = parser.css_first("div.profile-model-info img") or parser.css_first("div.profile-model img")
        image = (img_node.attributes.get("data-src") or img_node.attributes.get("src")) if img_node else None
        if image:
            thumbnail = f"https:{image}" if image.startswith("//") else image
        else:
            thumbnail = None
            logger.warning("Channel/Model thumbnail not found for %s", self.url)

        return {
            "name": name,
            "information": information,
            "thumbnail": thumbnail,
        }

    def videos(
        self,
        pages: int = 2,
        iterator_config: IteratorConfig | None = None,
    ) -> AsyncGenerator[ScrapeResult[Video], None]:
        url = self.url
        page_urls = [f"{url}?mode=async&function=get_block&block_id=list_videos_common_videos_list_norm&sort_by=post_date&from={page:02d}&_=1761740123131" for page in range(pages)]
        return scrape_stream(
            core=self.core,
            constructor=Video,
            target_page_urls=page_urls,
            item_extractor=extractor_html,
            iterator_config=iterator_config,
        )


@dataclass(kw_only=True, slots=True)
class Model(ChannelModelHelper):
    pass


@dataclass(kw_only=True, slots=True)
class Channel(ChannelModelHelper):
    pass


class Client:
    def __init__(self, core: BaseCore | None = None):
        if core is None:
            core = BaseCore()
        self.core = core or BaseCore()
        self.core.initialize_session()

    async def get_video(self, url: str, load_html: bool = True) -> Video:
        video = Video(url=url, core=self.core)
        if load_html:
            await video.load_sources("html")
        return video

    async def get_model(self, url: str, load_html: bool = True) -> Model:
        model = Model(url=url, core=self.core)
        if load_html:
            await model.load_sources("html")
        return model

    async def get_channel(self, url: str, load_html: bool = True) -> Channel:
        channel = Channel(url=url, core=self.core)
        if load_html:
            await channel.load_sources("html")
        return channel

    def search(
        self,
        query: str,
        pages: int = 2,
        iterator_config: IteratorConfig | None = None,
    ) -> AsyncGenerator[ScrapeResult[Video], None]:
        page_urls = [f"https://www.porntrex.com/search/{query}/?mode=async&function=get_block&block_id=list_videos_videos&q={query}&category_ids=&sort_by=relevance&from={page:02d}&_=1761771312451" for page in range(pages)]
        return scrape_stream(
            core=self.core,
            constructor=Video,
            target_page_urls=page_urls,
            item_extractor=extractor_html,
            iterator_config=iterator_config,
        )



def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PornTrex API Command Line Interface")
    parser.add_argument("--download", metavar="URL", type=str, help="URL to download from")
    parser.add_argument("--quality", metavar="best|half|worst", type=str, default="best", help="The video quality (best, half, worst)")
    parser.add_argument("--file", metavar="FILE", type=str, help="(Optional) Specify a file with URLs (separated with new lines)")
    parser.add_argument("--output", metavar="DIR", type=str, required=True, help="The output path (with filename or directory)")
    parser.add_argument("--no-title", metavar="True,False", type=str, nargs="?", const="True", default="False",
                        help="Whether to apply video title automatically to output path or not")
    return parser


async def run_main(args_list: list[str] | None = None):
    parser = create_parser()
    args = parser.parse_args(args_list)
    no_title = str_to_bool(args.no_title) if isinstance(args.no_title, str) else bool(args.no_title)
    config = DownloadConfigRAW(quality=args.quality, path=args.output, no_title=no_title)

    urls: list[str] = []
    if args.download:
        urls.append(args.download)
    if args.file:
        with open(args.file, "r") as f:
            urls.extend([line.strip() for line in f if line.strip()])

    if not urls:
        parser.print_help()
        return

    client = Client()
    for url in urls:
        print(f"Fetching video information for: {url}")
        try:
            video = await client.get_video(url, load_html=True)
            title = getattr(video, "title", None) or url
            print(f"Starting download for: {title}")
            await video.download(configuration=config)
            print(f"Download complete: {title}")
        except Exception as e:
            logger.exception("CLI failed while processing %s", url)
            print(f"Error downloading {url}: {e}")


def main():
    configure_app_logging(level=logging.INFO)
    try:
        asyncio.run(run_main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")


if __name__ == "__main__":
    main()
