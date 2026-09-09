from base_api import DownloadConfigRAW

from ..api import Client, Video
import pytest


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.mark.asyncio
async def test_all(client):
    video = await client.get_video("https://www.porntrex.com/video/2989480/i-have-two-big-titties-and-im-your-date")
    assert isinstance(video.title, str) and len(video.title) > 0
    assert isinstance(video.description, str) and len(video.description) > 0
    assert isinstance(video.duration, str) and len(video.duration) > 0
    assert isinstance(video.video_id, str) and len(video.video_id) > 0
    assert isinstance(video.author, str) and len(video.author) > 0
    assert isinstance(video.categories, list) and len(video.categories) > 0
    assert isinstance(video.tags, list) and len(video.tags) > 0
    assert isinstance(video.subscribers_count, str) and len(video.subscribers_count) > 0
    assert isinstance(video.lrc, str) and len(video.lrc) > 0
    assert isinstance(video.license_code, str) and len(video.license_code) > 0
    assert isinstance(video.views, str) and len(video.views) > 0
    assert isinstance(video.rnd, str) and len(video.rnd) > 0
    assert isinstance(video.thumbnail, str) and len(video.thumbnail) > 0
    stuff = DownloadConfigRAW(quality="worst")
    assert await video.download(stuff) is True


def test_extract_data_from_snippet(client):
    html_snippet = """<div class="content">
	<div class="block-video" id="block-chat">
		<div class="video-holder">
			<div class="player">
				<div class="player-holder">
								<div class="player-wrap" style="width: 100%; height: 0; padding-bottom: 56.338028169014%">
										<div id="kt_player" class="kt_player_dev embet-player-test kt-player is-no-touch is-splash is-mouseover is-paused"><div class="fp-poster"><img alt="Lesbian_illusion - PornHub #091" src="//ptx.cdntrex.com/contents/videos_screenshots/3325000/3325079/preview.mp4.jpg"></div></div>
								</div>
								<script type="text/javascript">
									var flashvars = {
										video_id: '3325079',
										video_title: 'Lesbian_illusion - PornHub #091',
										video_categories: 'Amateur, Lesbian, Pussy licking',
										video_tags: 'Lesbian_Illusion, -, pornhub, #091',
										license_code: '$535555517668914',
										lrc: '71773274',
										rnd: '1788870952',
										video_url: 'https://www.porntrex.com/get_file/16/fb6f20b0321eeb6d3d2983a6fc32c28674971e6942/3325000/3325079/3325079.mp4/',
										postfix: '.mp4',
										video_url_text: '480p',
										video_alt_url: 'https://www.porntrex.com/get_file/16/3346fd91d81ea9a9d5fd792bb19900c383a7517e11/3325000/3325079/3325079_720p.mp4/',
										video_alt_url_text: '720p HD',
										video_alt_url_hd: '1',
										video_alt_url2: 'https://www.porntrex.com/get_file/16/008f4bfe498a437fb9596ff3c5b0cdb02abc6b4070/3325000/3325079/3325079_1080p.mp4/',
										video_alt_url2_text: '1080p FHD',
										video_alt_url2_hd: '1',
										preview_url: '//ptx.cdntrex.com/contents/videos_screenshots/3325000/3325079/preview.jpg',
									};
								</script>
							</div>
			</div>
			<div class="video-info">
				<div class="info-holder">
					<div class="main-info-video">
						<div class="columns">
							<div class="column">
								<p class="title-video">Lesbian_illusion - PornHub #091</p>
							</div>
							<div class="column">
								<div class="btn-subscribe btn-subscribe-ajax">
									<a href="https://www.porntrex.com/login/" class="button">
										<span><i class="fa fa-user"></i> Subscribe</span>
										<div class="button-infow">21 163</div>
									</a>
								</div>
							</div>
						</div>
						<div class="info-block">
							Published by
							<div class="block-user">
								<div class="username">
									<a href="https://www.porntrex.com/members/5420142/">russell123</a>
									<i class="fa fa-check-circle"></i>
								</div>
							</div>
							<div class="item">
								<span><i class="fa fa-calendar"></i> <em class="badge">1 minute ago</em></span>
								<span><i class="fa fa-eye"></i> <em class="badge">0</em></span>
								<span><i class="fa fa-clock-o"></i> <em class="badge">5min 16sec</em></span>
							</div>
						</div>
					</div>
					<div id="tab_video_info" class="tab-content" style="display: block;">
						<div class="block-details">
							<div class="info">
								<div class="item">
									<span class="title-item">Categories:</span>
									<div class="items-holder js-categories">
										<a class="js-cat" href="https://www.porntrex.com/categories/amateur/">Amateur</a>
										<a class="js-cat" href="https://www.porntrex.com/categories/lesbian/">Lesbian</a>
										<a class="js-cat" href="https://www.porntrex.com/categories/pussy-licking/">Pussy licking</a>
									</div>
								</div>
								<div class="item">
									<span class="title-item">Tags:</span>
									<div class="items-holder">
										<a href="https://www.porntrex.com/tags/lesbian-illusion/">Lesbian_Illusion</a>
										<a href="https://www.porntrex.com/tags/44fe833cf3d162efe8f1f998bc14416c/">-</a>
										<a href="https://www.porntrex.com/tags/pornhub/">pornhub</a>
										<a href="https://www.porntrex.com/tags/091/">#091</a>
									</div>
								</div>
								<div class="videodesc item">
									<span class="title-item">Description:</span>
									<div class="items-holder">
										<em style="font-size: 0.9em;" class="des-link">Lesbian_illusion - PornHub #091</em>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
</div>"""

    video = Video(url="https://www.porntrex.com/video/3325079/lesbian-illusion-pornhub-0912", core=client.core)
    data = video._extract_data(html_snippet)
    assert data["title"] == "Lesbian_illusion - PornHub #091"
    assert data["video_id"] == "3325079"
    assert data["author"] == "russell123"
    assert data["publish_date"] == "1 minute ago"
    assert data["views"] == "0"
    assert data["duration"] == "5min 16sec"
    assert data["description"] == "Lesbian_illusion - PornHub #091"
    assert data["subscribers_count"] == "21 163"
    assert data["categories"] == ["Amateur", "Lesbian", "Pussy licking"]
    assert data["tags"] == ["Lesbian_Illusion", "-", "pornhub", "#091"]
    assert data["thumbnail"] == "https://ptx.cdntrex.com/contents/videos_screenshots/3325000/3325079/preview.jpg"
    assert data["video_qualities"] == ["480", "720", "1080"]
    assert len(data["direct_download_urls"]) == 3

    # Fallback test without flashvars script block
    html_without_flashvars = html_snippet.split("<script")[0] + html_snippet.split("</script>")[1]
    fallback_data = video._extract_data(html_without_flashvars)
    assert fallback_data["title"] == "Lesbian_illusion - PornHub #091"
    assert fallback_data["author"] == "russell123"
    assert fallback_data["categories"] == ["Amateur", "Lesbian", "Pussy licking"]
    assert fallback_data["tags"] == ["Lesbian_Illusion", "-", "pornhub", "#091"]
    assert fallback_data["thumbnail"] == "https://ptx.cdntrex.com/contents/videos_screenshots/3325000/3325079/preview.mp4.jpg"
    assert fallback_data["publish_date"] == "1 minute ago"
    assert fallback_data["views"] == "0"
    assert fallback_data["duration"] == "5min 16sec"
    assert fallback_data["description"] == "Lesbian_illusion - PornHub #091"
    assert fallback_data["subscribers_count"] == "21 163"

