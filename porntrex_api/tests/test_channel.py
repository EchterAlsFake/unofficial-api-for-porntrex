from .. import Client, Video
from base_api.base import BaseCore
import pytest

@pytest.mark.asyncio
async def test_all():

    core = BaseCore()
    core.configuration.videos_concurrency = 1
    core.configuration.pages_concurrency = 1

    client = Client(core)
    model = await client.get_model("https://www.porntrex.com/channels/nubile-films/")

    assert isinstance(model.name, str) and len(model.name) > 0
    assert isinstance(model.information, dict) and len(model.information) > 0

    idx = 0
    async for video in model.videos():
        idx += 1
        assert isinstance(video.unwrap().title, str)

        if idx >= 5:
            break


def test_extract_html_from_snippet():
    html_snippet = """<div class="content common_list" data-tit="VirginMassage Full HD and 4K Porn Videos - PornTrex" data-dir="">
			<div class="profile-model dvd-info">
					<img src="//ptx.cdntrex.com/contents/dvds/358/cb2_358.jpg?v=400" alt="VirginMassage" class="cover-img">
		  
		<div class="profile-model-info">
			<div class="img-holder">
				<div class="name">
					<h1>
						<a href="https://www.porntrex.com/channels/virginmassage/">VirginMassage</a>
					</h1>
				</div> 
				<img src="//ptx.cdntrex.com/contents/dvds/358/cf1_358.jpg" alt="VirginMassage">
			</div>
			<div class="model-btns">
				<div class="btn-subscribe-ajax">
																		<a href="https://www.porntrex.com/login/" class="button item subscribe"><i class="fa fa-user-plus"></i>Subscribe</a>
															</div>
				<div>
					<a href=".block-comments" class="item button">
						<i class="fa fa-comment-o"></i>Comments (3)
					</a>
				</div>
							</div>
		</div>
	</div>
		<div class="main-content">
					<div class="sidebar  sidebar-dvd">
									<div class="info">
												<div class="join">
		<a class="buttonBase orangeButton" id="link" href="https://www.virginmassage.com/" target="_blank" rel="noopener nofollow">Join virginmassage Now</a>
	</div>
	<p class="rang-dvd"><i class="fa fa-line-chart"></i><span>PORNTREX.COM Rank:</span> 9.7</p>
	<p class="rang-dvd"><i class="fa fa-video-camera"></i><span>Total Videos:</span> 16</p>
	<p class="rang-dvd"><i class="fa fa-user-plus"></i><span>Followers:</span> 12</p>
	<p><i class="fa fa-eye"></i><span>Video Views:</span> 
					0
	</p>
	<hr>
	<p class="rang-dvd"><span>About:</span> Welcome to the amazing world of erotic massage.</p>
	<hr>
	<div class="list-models related" id="list_dvds_related_channels_list">
		<div class="info"><p>Related to SexSinners</p></div>
	</div>
</div>
</div>
</div>
</div>"""

    from ..api import Channel
    channel = Channel(url="https://www.porntrex.com/channels/virginmassage/", core=BaseCore())
    data = channel._extract_html(html_snippet)
    assert data["name"] == "VirginMassage"
    assert data["thumbnail"] == "https://ptx.cdntrex.com/contents/dvds/358/cf1_358.jpg"
    assert data["information"]["PORNTREX.COM Rank"] == "9.7"
    assert data["information"]["Total Videos"] == "16"
    assert data["information"]["Followers"] == "12"
    assert data["information"]["Video Views"] == "0"
    assert data["information"]["About"] == "Welcome to the amazing world of erotic massage."


