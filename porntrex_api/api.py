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
from base_api import (
    BaseCore,
    BaseMedia,
    DownloadConfigRAW,
    ErrorAction,
    ErrorHandler,
    ErrorMode,
    Helper,
    MediaLoadError,
    MediaLoadErrors,
    ResultOrder,
    RetryPolicy,
    ScrapeErrorContext,
    ScrapeResult,
    media_field,
)
from base_api.modules.static_functions import choose_quality_from_list,  normalize_quality_value
from base_api.modules.errors import (
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


def _contains_resource_gone(error: BaseException) -> bool:
    if isinstance(error, ResourceGone):
        return True
    if isinstance(error, MediaLoadError):
        return _contains_resource_gone(error.original_error)
    if isinstance(error, MediaLoadErrors):
        return any(_contains_resource_gone(item) for item in error.errors)
    return False


async def on_error(context: ScrapeErrorContext) -> ErrorAction:
    logger.error(
        "URL: %s, ERROR: %s, Attempt: %s",
        context.url,
        context.error,
        context.attempt,
    )

    if _contains_resource_gone(context.error):
        return ErrorAction.SKIP

    return ErrorAction.RETRY


async def get_html_content(core: BaseCore, url: str) -> str:
    try:
        return await core.fetch_text(url)

    except HTTPStatusError as e:
        if e.status_code == 404:
            raise NotFound(f"Server returned 404 for: {url}") from e
        raise NetworkError(str(e)) from e

    except NetworkRequestError as e:
        raise NetworkError(str(e)) from e

    except InvalidProxy as e:
        raise ProxyError(str(e)) from e

    except BotProtectionDetected as e:
        raise BotDetection(str(e)) from e

    except UnknownError as e:
        raise UnknownNetworkError(str(e)) from e


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

    def _extract_data(self, html_content: str ) -> dict:
        parser = LexborHTMLParser(html_content)
        _video_metadata = parser.css_first("div.video-info").css_first("div.item")

        m = re.search(r"var\s+flashvars\s*=\s*({.*?})\s*;", html_content, re.S)
        obj_literal = m.group(1)
        json_data = json5.loads(obj_literal)

        title = json_data["video_title"]
        video_id = json_data["video_id"]
        categories = json_data["video_categories"].split(",")
        tags = json_data["video_tags"].split(",")
        license_code = json_data["license_code"]
        lrc = json_data["lrc"]
        rnd = json_data["rnd"]
        author = parser.css_first("div.username").css_first("a").text(strip=True)
        publish_date = _video_metadata.css_first("em").text(strip=True)
        views = _video_metadata.css("em")[1].text(strip=True)
        duration = _video_metadata.css("em")[2].text(strip=True)
        description = parser.css_first("em.des-link").text(strip=True)
        subscribers_count = parser.css_first("div.button-infow").text(strip=True)
        image = json_data["preview_url"]
        thumbnail = f"https:{image}"

        direct_download_urls = self.get_direct_download_urls(json_data)
        video_qualities = self.get_video_qualities(json_data)

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
            "video_qualities": video_qualities
        }

    @staticmethod
    def _extract_height_for_key(key: str, url: str, json_data: dict) -> int | None:
        """
        Try to get the numeric height from "<key>_text" first, then from the URL pattern.
        """
        # 1) From "<key>_text" if present (e.g., "720p HD")
        label = json_data.get(f"{key}_text")
        if label:
            m = PATTERN_RESOLUTION_TEXT.search(label)
            if m:
                return int(m.group(1))

        # 2) From the URL itself if it ends with "..._720p.mp4"
        m = PATTERN_RESOLUTION_IN_URL.search(url)
        if m:
            return int(m.group(1))

        # 3) Special-case fallback: the base "video_url" sometimes lacks "_480p" in the URL;
        #    use "video_url_text" if available.
        if key == "video_url":
            txt = json_data.get("video_url_text")
            if txt:
                m = PATTERN_RESOLUTION_TEXT.search(txt)
                if m:
                    return int(m.group(1))

        return None

    def _collect_height_url_pairs(self, json_data: dict) -> list[tuple[int, str]]:
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

            h = self._extract_height_for_key(k, v, json_data)
            if h is not None:
                by_height[h] = v

        # Sort by ascending height
        return sorted(by_height.items(), key=lambda kv: kv[0])

    def get_video_qualities(self, json_data: dict) -> list:
        """
        :return: (list[str]) available qualities as e.g. ["480", "720", "1080", "2160"]
        """
        pairs = self._collect_height_url_pairs(json_data)
        heights = [str(h) for h, _ in pairs]
        return heights

    def get_direct_download_urls(self, json_data: dict) -> list:
        """
        :return: (list[str]) direct MP4 URLs aligned in ascending order of quality.
                 Ordering matches the sorted `video_qualities`.
        """
        pairs = self._collect_height_url_pairs(json_data)
        urls = [url for _, url in pairs]
        return urls

    async def download(self, configuration: DownloadConfigRAW) -> bool:
        await self.load_fields("direct_download_urls", "video_qualities", "title")
        config = copy.deepcopy(configuration)
        cdn_urls = self.direct_download_urls
        quals = self.video_qualities  # e.g., ["480", "720", "1080", "2160"]

        qn = normalize_quality_value(config.quality)
        chosen_height = choose_quality_from_list(quals, qn)

        quality_url_map = {int(q): url for q, url in zip(quals, cdn_urls)}
        download_url = quality_url_map[chosen_height]

        if not config.no_title:
            safe_title = f"{self.title}.mp4"
            config.path = os.path.join(config.path, safe_title)

        try:
            await self.core.legacy_download(url=download_url, configuration=config)
            return True

        except Exception as e:
            raise DownloadFailed(str(e))


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

    @staticmethod
    def _extract_html(html_content: str) -> dict:
        parser = LexborHTMLParser(html_content)
        _info_container = parser.css_first("div.sidebar").css_first("div.info")

        name = parser.css_first("div.name").css_first("a").text(strip=True)
        information = {}

        info_stuff = _info_container.css("p")
        for p in info_stuff:
            _list = p.text().split(":")
            try:
                information[_list[0]] = _list[1]

            except IndexError:
                break # No more useful data

        try:
            image = parser.css_first("div.profile-model-info").css_first("img").attributes.get("data-src")

        except AttributeError:
            image = parser.css_first("div.profile-model-info").css_first("img").attributes.get("src")

        thumbnail = f"https:{image}"

        return {
            "name": name,
            "information": information,
            "thumbnail": thumbnail,
        }

    async def videos(self, pages: int = 2, videos_concurrency: int | None = None, pages_concurrency: int | None = None,
                     on_video_error: ErrorHandler | None = on_error,
                     on_page_error: ErrorHandler | None = None,
                     keep_original_order: bool = False,
                     load_html: bool = False) -> AsyncGenerator[ScrapeResult, None]:
        url = self.url
        page_urls = [f"{url}?mode=async&function=get_block&block_id=list_videos_common_videos_list_norm&sort_by=post_date&from={page:02d}&_=1761740123131" for page in range(pages)]
        videos_concurrency = videos_concurrency or self.core.configuration.videos_concurrency
        pages_concurrency = pages_concurrency or self.core.configuration.pages_concurrency
        assert videos_concurrency and pages_concurrency
        helper = Helper(core=self.core, constructor=Video)
        stream = helper.iterator(
            target_page_urls=page_urls,
            item_extractor=extractor_html,
            max_item_concurrency=videos_concurrency,
            max_page_concurrency=pages_concurrency,
            load_sources=("html",) if load_html else (),
            order=ResultOrder.ORIGINAL if keep_original_order else ResultOrder.COMPLETION,
            item_retry=RetryPolicy(max_attempts=3),
            page_retry=RetryPolicy(max_attempts=3),
            page_error_mode=ErrorMode.SKIP,
            item_error_handler=on_video_error,
            page_error_handler=on_page_error,
        )
        async with stream:
            async for result in stream:
                yield result


@dataclass(kw_only=True, slots=True)
class Model(ChannelModelHelper):
    pass


@dataclass(kw_only=True, slots=True)
class Channel(ChannelModelHelper):
    pass


class Client:
    def __init__(self, core: BaseCore = BaseCore()):
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

    async def search(self, query: str, pages: int = 2,
                videos_concurrency: int | None = None, pages_concurrency: int | None = None,
                     on_video_error: ErrorHandler | None = on_error,
                     on_page_error: ErrorHandler | None = None,
                     keep_original_order: bool = False,
                     load_html: bool = False
                     ) -> AsyncGenerator[ScrapeResult, None]:

        page_urls = [f"https://www.porntrex.com/search/{query}/?mode=async&function=get_block&block_id=list_videos_videos&q={query}&category_ids=&sort_by=relevance&from={page:02d}&_=1761771312451" for page in range(pages)]
        videos_concurrency = videos_concurrency or self.core.configuration.videos_concurrency
        pages_concurrency = pages_concurrency or self.core.configuration.pages_concurrency
        assert videos_concurrency and pages_concurrency
        helper = Helper(core=self.core, constructor=Video)
        stream = helper.iterator(
            target_page_urls=page_urls,
            item_extractor=extractor_html,
            max_item_concurrency=videos_concurrency,
            max_page_concurrency=pages_concurrency,
            load_sources=("html",) if load_html else (),
            order=ResultOrder.ORIGINAL if keep_original_order else ResultOrder.COMPLETION,
            item_retry=RetryPolicy(max_attempts=3),
            page_retry=RetryPolicy(max_attempts=3),
            page_error_mode=ErrorMode.SKIP,
            item_error_handler=on_video_error,
            page_error_handler=on_page_error,
        )
        async with stream:
            async for result in stream:
                yield result
