"""Create a portable ZIP without including user files, logs or test audio."""
from pathlib import Path
import hashlib
import zipfile

root = Path(__file__).resolve().parent.parent
executable = root/'dist'/'KEYWAVE.exe'
if not executable.is_file():
    raise SystemExit('Build KEYWAVE.exe before packaging')
destination = root/'dist'/'KEYWAVE-Windows-x64.zip'
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    archive.write(executable,'KEYWAVE.exe')
    for name in ('README.md','VERIFICATION.md','LICENSE','THIRD_PARTY_NOTICES.md'):
        archive.write(root/name,name)
with destination.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
destination.with_suffix('.zip.sha256').write_text(f'{digest}  {destination.name}\n', encoding='ascii')
print(f'{destination.name}: {destination.stat().st_size / 1024**2:.1f} MiB; SHA256 {digest}')
