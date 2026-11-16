"""Fetch a pinned official Node runtime and verify its published SHA-256."""
from pathlib import Path
import hashlib
import io
import urllib.request
import zipfile

root = Path(__file__).resolve().parent.parent
version = 'v22.16.0'
name = f'node-{version}-win-x64'
base = f'https://nodejs.org/dist/{version}/'
runtime = root/'runtime'
runtime.mkdir(exist_ok=True)
if not (runtime/'node.exe').exists():
    hashes = urllib.request.urlopen(base+'SHASUMS256.txt', timeout=60).read().decode()
    expected = next(line.split()[0] for line in hashes.splitlines() if line.split()[-1] == name+'.zip')
    data = urllib.request.urlopen(base+name+'.zip', timeout=120).read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError('Node archive checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        (runtime/'node.exe').write_bytes(archive.read(name+'/node.exe'))
        (root/'licenses'/'Node-LICENSE.txt').write_bytes(archive.read(name+'/LICENSE'))
print('YouTube JavaScript runtime ready')
