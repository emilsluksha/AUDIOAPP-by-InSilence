"""Generate the original geometric KEYWAVE mark and bundled license texts."""
from pathlib import Path
import importlib.metadata
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parent.parent
assets = root / 'assets'
assets.mkdir(exist_ok=True)
image = Image.new('RGBA', (512, 512), '#0D0A14')
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((16, 16, 496, 496), radius=108, fill='#21182E', outline='#49315F', width=4)
heights = [60, 130, 225, 330, 190, 100, 245, 150, 60]
for i, height in enumerate(heights):
    t = i/(len(heights)-1)
    color = tuple(round(a*(1-t)+b*t) for a,b in zip((139,92,246),(244,114,182)))
    x = 75 + i*42
    draw.rounded_rectangle((x, 256-height//2, x+25, 256+height//2), radius=12, fill=color)
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
