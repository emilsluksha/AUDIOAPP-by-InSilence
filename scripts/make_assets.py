"""Prepare the supplied KEYWAVE logo and collect bundled license texts."""
from pathlib import Path
import importlib.metadata
from PIL import Image

root = Path(__file__).resolve().parent.parent
assets = root / 'assets'
assets.mkdir(exist_ok=True)
# Keep the user-supplied logo across local and CI builds.
image = Image.open(assets/'keywave-logo.png').convert('RGBA')
image.save(assets/'keywave.png')
image.save(assets/'keywave.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
licenses = root/'licenses'
licenses.mkdir(exist_ok=True)
for dist in importlib.metadata.distributions():
    name = dist.metadata['Name']
    for file in dist.files or []:
        if any(term in Path(str(file)).name.lower() for term in ('license', 'copying', 'lgpl', 'gpl', 'bsd', 'apache')) and str(file).endswith(('.txt','.md','.rst','LICENSE','COPYING')):
            source = dist.locate_file(file)
            if source.is_file() and source.stat().st_size < 2_000_000:
                try:
                    text = source.read_text(encoding='utf-8')
                    (licenses/(name+'-'+source.name)).write_text(text, encoding='utf-8')
                except UnicodeError:
                    continue
