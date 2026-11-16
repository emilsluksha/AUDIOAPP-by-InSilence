from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
from keywave.core import AudioError, Progress, Cancelled
from keywave.downloader import youtube_url, download_mp3


@pytest.mark.parametrize('url', ['https://youtu.be/BaW_jenozKc', 'https://www.youtube.com/watch?v=BaW_jenozKc&list=example', 'https://music.youtube.com/watch?v=BaW_jenozKc', 'https://youtube.com/shorts/BaW_jenozKc'])
def test_youtube_urls(url):
    assert youtube_url(url) == 'https://www.youtube.com/watch?v=BaW_jenozKc'


@pytest.mark.parametrize('url', ['file:///test', 'https://youtube.com.evil.test/watch?v=BaW_jenozKc', 'https://youtube.com/playlist?list=123', 'https://youtu.be/no', 'https://user:password@youtube.com/watch?v=BaW_jenozKc'])
def test_invalid_youtube_urls(url):
    with pytest.raises(AudioError, match='youtube_invalid'):
        youtube_url(url)


def test_download_encode_and_no_overwrite(tmp_path, monkeypatch):
    import yt_dlp
    import keywave.downloader as module
    node = tmp_path/'node.exe'
    node.touch()
    monkeypatch.setattr(module, 'resource', lambda _: node)
    class DownloadFixture:
        def __init__(self, options):
            self.options = options
            self.path = Path(options['outtmpl'].replace('%(ext)s', 'wav'))
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def extract_info(self, url, download):
            assert self.options['noplaylist']
            t = np.arange(22050)/22050
            sf.write(self.path, .1*np.sin(2*np.pi*440*t), 22050)
            self.options['progress_hooks'][0]({'downloaded_bytes': 100, 'total_bytes': 100})
            return {'title':'Test audio', 'id':'BaW_jenozKc'}
        def prepare_filename(self, info):
            return str(self.path)
    monkeypatch.setattr(yt_dlp, 'YoutubeDL', DownloadFixture)
    first = Path(download_mp3('https://youtu.be/BaW_jenozKc', str(tmp_path)))
    before = first.read_bytes()
    second = Path(download_mp3('https://youtu.be/BaW_jenozKc', str(tmp_path)))
    assert second != first and first.read_bytes() == before
    assert sf.info(second).duration > .9
    assert not list(tmp_path.glob('.keywave-download-*'))


def test_download_cancelled_before_network(tmp_path):
    progress = Progress()
    progress.event.set()
    with pytest.raises(Cancelled):
        download_mp3('https://youtu.be/BaW_jenozKc', str(tmp_path), progress=progress)


def test_video_quality_and_drm():
    from keywave.downloader import choose_video
    formats = [{'format_id':str(h),'height':h,'vcodec':'h264','fps':30} for h in (720,1080,1440,2160)]
    assert choose_video(formats,None)['height'] == 2160
    assert choose_video(formats,1080)['height'] == 1080
    formats[-1]['has_drm'] = True
    assert choose_video(formats,None)['height'] == 1440
    with pytest.raises(AudioError):
        choose_video(formats,360)


def test_mp4_merge_real_ffmpeg(tmp_path,monkeypatch):
    import shutil
    import yt_dlp
    import keywave.downloader as module
    from keywave.audio import run_codec
    node = tmp_path/'node.exe'
    node.touch()
    monkeypatch.setattr(module,'resource',lambda _:node)
    video = tmp_path/'fixture.mp4'
    run_codec(['-y','-f','lavfi','-i','color=c=purple:s=160x90:r=25:d=1','-an','-c:v','libx264',str(video)],Progress())
    audio = tmp_path/'fixture.wav'
    t = np.arange(22050)/22050
    sf.write(audio,.1*np.sin(2*np.pi*440*t),22050)
    class VideoFixture:
        def __init__(self,opts):
            self.opts = opts
        def __enter__(self):
            return self
        def __exit__(self,*args):
            return False
        def extract_info(self,url,download):
            info = {'title':'Merge fixture','id':'BaW_jenozKc','formats':[{'format_id':'v','height':1080,'vcodec':'h264','acodec':'none'}]}
            if download:
                is_video = self.opts['format'] == 'v'
                self.path = Path(self.opts['outtmpl'].replace('%(ext)s','mp4' if is_video else 'wav'))
                shutil.copyfile(video if is_video else audio,self.path)
                self.opts['progress_hooks'][0]({'downloaded_bytes':100,'total_bytes':100,'speed':100,'eta':0})
            return info
        def prepare_filename(self,info):
            return str(self.path)
    monkeypatch.setattr(yt_dlp,'YoutubeDL',VideoFixture)
    output = module.download_media('https://youtu.be/BaW_jenozKc',str(tmp_path),'mp4',1080)
    assert Path(output).stat().st_size > 1000
    run_codec(['-i',output,'-map','0:v:0','-map','0:a:0','-f','null','-'],Progress())
