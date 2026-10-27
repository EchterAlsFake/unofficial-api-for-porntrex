import pytest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from porntrex_api import api


def test_search_query_is_one_value():
    client = object.__new__(api.Client)
    client.core = object()
    with patch.object(api, "scrape_stream") as stream:
        client.search("a&b/# 日本", pages=2)
    urls = stream.call_args.kwargs["target_page_urls"]
    assert len(urls) == len(set(urls)) == 2
    for url in urls:
        assert parse_qs(urlsplit(url).query)["q"] == ["a&b/# 日本"]
        assert not urlsplit(url).fragment


def test_search_pages_start_at_one():
    client = object.__new__(api.Client)
    client.core = object()
    with patch.object(api, "scrape_stream") as stream:
        client.search("test", pages=2)
    assert [
        parse_qs(urlsplit(u).query)["from"]
        for u in stream.call_args.kwargs["target_page_urls"]
    ] == [["01"], ["02"]]


@pytest.mark.parametrize("suffix", ["?token=abc", "#fragment", "?token=abc#fragment"])
def test_signed_download_urls(suffix):
    url = "https://cdn.example/test_720p.mp4" + suffix
    assert api.Video.get_video_qualities({"video_url": url}) == ["720"]
    assert api.Video.get_direct_download_urls({"video_url": url}) == [url]


@pytest.mark.asyncio
async def test_cli_closes_session_and_reports_false_download(capsys, tmp_path):
    from unittest.mock import AsyncMock, MagicMock
    from base_api import BaseCore
    from base_api.modules.config import RuntimeConfig

    core = BaseCore(RuntimeConfig())
    video = MagicMock(title="Example", length="10", url="https://example.com/video")
    video.load_fields = AsyncMock()
    video.download = AsyncMock(return_value=False)
    client = MagicMock()
    client.get_video = AsyncMock(return_value=video)
    with (
        patch.object(api, "BaseCore", return_value=core),
        patch.object(api, "Client", return_value=client),
    ):
        await api.run_main(
            ["--download", "https://example.com/video", "--output", str(tmp_path)]
        )
    assert core.session is None
    output = capsys.readouterr().out
    assert "Download complete:" not in output
    assert "Done ->" not in output
    assert "Download did not complete" in output
