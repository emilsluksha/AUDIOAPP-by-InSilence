"""Opt-in real network check of the exact downloader shipped inside the EXE."""
import json
import logging
from pathlib import Path
import sys
import traceback


def run(url, folder):
    from .downloader import preview, download_media
    from .audio import run_codec
    from .core import Progress
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(folder/'downloader.log', encoding='utf-8')
    logging.getLogger().addHandler(handler)
    report = {'frozen': bool(getattr(sys, 'frozen', False)), 'ok': False}
    try:
        info = preview(url)
        report['title'] = info['title']
        report['duration'] = info['duration']
        for mode, quality in [('mp3', 192), ('mp4', 720)]:
            path = download_media(url, str(folder), mode, quality)
            run_codec(['-i', path, '-t', '1', '-map', '0:a:0', '-f', 'null', '-'], Progress())
            if mode == 'mp4':
                run_codec(['-i', path, '-t', '1', '-map', '0:v:0', '-f', 'null', '-'], Progress())
            report[mode] = path
        report['ok'] = True
    except Exception as error:
        report['error'] = traceback.format_exc()
        report['nested_errors'] = [''.join(traceback.format_exception(type(e), e, e.__traceback__))
                                   for e in getattr(error, 'unexpected_errors', [])]
        logging.exception('Packaged downloader check failed')
    finally:
        (folder/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        logging.getLogger().removeHandler(handler)
        handler.close()
    return 0 if report['ok'] else 1
