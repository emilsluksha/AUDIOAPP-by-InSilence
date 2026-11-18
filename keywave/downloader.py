"""Single-video downloader. No cookies, login, DRM or access restriction bypass."""
from pathlib import Path
import logging
import os
import re
import shutil
import tempfile
import urllib.request
from urllib.parse import urlparse, parse_qs

from .audio import run_codec, ffmpeg
from .core import AudioError, Cancelled, Progress, resource


def youtube_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in ('https','http') or parsed.username or parsed.password:
        raise AudioError('youtube_invalid')
    host = (parsed.hostname or '').lower()
    if host == 'youtu.be':
        identifier = parsed.path.strip('/')
    elif host in ('youtube.com','www.youtube.com','m.youtube.com','music.youtube.com'):
        parts = parsed.path.strip('/').split('/')
        identifier = parse_qs(parsed.query).get('v',[''])[0] if parsed.path == '/watch' else (parts[1] if len(parts) == 2 and parts[0] in ('shorts','embed','live') else '')
    else:
        raise AudioError('youtube_invalid')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',identifier):
        raise AudioError('youtube_invalid')
    return 'https://www.youtube.com/watch?v='+identifier


def reject_live(info, *, incomplete=False):
    if info.get('is_live') or info.get('live_status') in ('is_live','is_upcoming'):
        return 'Live streams are not supported'
    return None


def options(progress: Progress):
    node = resource('runtime/node.exe')
    node_path = str(node) if node.is_file() else shutil.which('node')
    if not node_path:
        raise AudioError('youtube_runtime')
    return {'noplaylist':True,'quiet':True,'noprogress':True,
        'logger':logging.getLogger('keywave.youtube'),
        'ffmpeg_location':ffmpeg(),
        'no_warnings':False,'socket_timeout':25,
        'retries':4,'fragment_retries':4,'extractor_retries':3,
        'file_access_retries':3,'cachedir':False,'restrictfilenames':True,
        'match_filter':reject_live,'js_runtimes':{'node':{'path':node_path}},
        'remote_components':[], 'skip_unavailable_fragments':False}


def explain_download_error(error: Exception) -> AudioError:
    """Preserve the real downloader failure instead of the unhelpful 'Failed'."""
    reason = re.sub(r'\x1b\[[0-9;]*m', '', str(error)).strip()
    if reason.startswith('ERROR: '):
        reason = reason[7:]
    # yt-dlp can include large extractor traces; keep the visible notification brief.
    reason = ' '.join(reason.split())[:450]
    return AudioError('youtube_unavailable' + (': ' + reason if reason else ''))


def thumbnail_bytes(info, progress):
    parsed = urlparse(info.get('thumbnail',''))
    if parsed.scheme != 'https' or not (parsed.hostname or '').endswith(('.ytimg.com','.ggpht.com')):
        return b''
    try:
        progress.check()
        with urllib.request.urlopen(parsed.geturl(),timeout=10) as response:
            image = response.read(2_000_001)
        progress.check()
        return image if len(image) <= 2_000_000 else b''
    except (OSError,ValueError):
        return b''


def preview(url: str, progress: Progress | None = None) -> dict:
    import yt_dlp
    progress = progress or Progress()
    url = youtube_url(url)
    progress.update(5,'youtube_connecting')
    try:
        with yt_dlp.YoutubeDL(options(progress)) as downloader:
            info = downloader.extract_info(url,download=False)
        progress.check()
        if not info or reject_live(info):
            raise AudioError('youtube_unavailable')
        heights = sorted({int(f['height']) for f in info.get('formats',[]) if f.get('height') and not f.get('has_drm')})
        result = {'title':info.get('title','YouTube'),'duration':info.get('duration'),
                  'thumbnail':thumbnail_bytes(info,progress),'heights':heights}
        progress.update(100,'ready')
        return result
    except yt_dlp.utils.DownloadError as error:
        progress.check()
        logging.warning('YouTube preview failed: %s',error)
        raise explain_download_error(error) from error


def choose_video(formats: list[dict], height: int | None):
    available = [f for f in formats if f.get('vcodec','none') != 'none' and f.get('height')
                 and not f.get('has_drm') and (height is None or f['height'] <= height)]
    if not available:
        raise AudioError('youtube_quality_unavailable')
    return max(available,key=lambda f:(f.get('height',0),f.get('fps') or 0,f.get('tbr') or 0))


def download_media(url: str, folder: str, mode: str = 'mp3', quality: int = 192,
                   progress: Progress | None = None) -> str:
    import yt_dlp
    from yt_dlp.utils import sanitize_filename
    progress = progress or Progress()
    progress.check()
    url = youtube_url(url)
    if mode not in ('mp3','mp4') or (mode == 'mp3' and quality not in (128,192,256,320)) or (mode == 'mp4' and quality not in (0,720,1080,1440,2160)):
        raise AudioError('invalid_settings')
    directory = Path(folder).expanduser().resolve()
    directory.mkdir(parents=True,exist_ok=True)
    base_options = options(progress)
    progress.update(1,'youtube_connecting')
    with tempfile.TemporaryDirectory(prefix='.keywave-download-',dir=directory) as temp:
        def fetch(format_id, name, start=5, span=70):
            def hook(status):
                progress.check()
                total = status.get('total_bytes') or status.get('total_bytes_estimate')
                size = status.get('downloaded_bytes',0)
                progress.update(min(start+span,start+int(span*size/total)) if total else start,'youtube_downloading')
                progress.details({'speed':status.get('speed'),'eta':status.get('eta'),'downloaded':size})
            opts = {**base_options,'format':format_id,'outtmpl':str(Path(temp)/(name+'.%(ext)s')),
                    'progress_hooks':[hook]}
            with yt_dlp.YoutubeDL(opts) as downloader:
                info = downloader.extract_info(url,download=True)
                progress.check()
                if not info:
                    raise AudioError('youtube_unavailable')
                path = Path(downloader.prepare_filename(info))
                if not path.is_file():
                    raise AudioError('youtube_unavailable')
                return path,info
        try:
            if mode == 'mp3':
                source,info = fetch('bestaudio/best','audio')
                inputs = ['-i',str(source),'-vn','-map','0:a:0','-c:a','libmp3lame','-b:a',f'{quality}k']
            else:
                with yt_dlp.YoutubeDL(base_options) as downloader:
                    metadata = downloader.extract_info(url,download=False)
                progress.check()
                if not metadata or reject_live(metadata):
                    raise AudioError('youtube_unavailable')
                selected = choose_video(metadata.get('formats',[]),quality or None)
                video,info = fetch(selected['format_id'],'video',5,50)
                if selected.get('acodec','none') == 'none':
                    audio,_ = fetch('bestaudio/best','audio',55,23)
                    inputs = ['-i',str(video),'-i',str(audio),'-map','0:v:0','-map','1:a:0']
                else:
                    inputs = ['-i',str(video),'-map','0:v:0','-map','0:a:0']
                inputs += ['-c:v','copy','-c:a','aac','-b:a','256k','-movflags','+faststart']
            progress.details({'title':info.get('title','YouTube'),'duration':info.get('duration')})
        except Cancelled:
            raise
        except yt_dlp.utils.DownloadError as error:
            progress.check()
            logging.warning('YouTube download failed: %s',error)
            raise explain_download_error(error) from error
        progress.update(82,'youtube_converting' if mode == 'mp3' else 'youtube_merging')
        encoded = Path(temp)/('converted.'+mode)
        run_codec(['-y',*inputs,'-metadata','title='+str(info.get('title','YouTube')),str(encoded)],progress)
        progress.check()
        name = sanitize_filename(str(info.get('title') or 'YouTube'),restricted=False)[:100].strip(' .') or 'YouTube'
        stem = f'{name} [{info["id"]}]'
        for number in range(10000):
            destination = directory/(stem+(f' ({number})' if number else '')+'.'+mode)
            try:
                if destination.exists():
                    continue
                os.rename(encoded,destination)
                break
            except FileExistsError:
                continue
        else:
            raise AudioError('write_error')
        progress.update(100,'youtube_done')
        return str(destination)


def download_mp3(url: str, folder: str, bitrate: int = 192, progress: Progress | None = None) -> str:
    return download_media(url,folder,'mp3',bitrate,progress)
