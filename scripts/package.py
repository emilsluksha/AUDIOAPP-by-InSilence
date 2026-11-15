"""Create a portable ZIP without including user files, logs or test audio."""
from pathlib import Path
import hashlib
import shutil
import zipfile

root = Path(__file__).resolve().parent.parent
bundle = root/'dist'/'KEYWAVE'
if not (bundle/'KEYWAVE.exe').is_file():
    raise SystemExit('Build KEYWAVE.exe before packaging')
for name in ('README.md', 'VERIFICATION.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md'):
    shutil.copy2(root/name, bundle/name)
destination = root/'dist'/'KEYWAVE-Windows-x64.zip'
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in sorted(bundle.rglob('*')):
        if path.is_file():
            archive.write(path, path.relative_to(bundle.parent))
with destination.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
destination.with_suffix('.zip.sha256').write_text(f'{digest}  {destination.name}\n', encoding='ascii')
print(f'{destination.name}: {destination.stat().st_size / 1024**2:.1f} MiB; SHA256 {digest}')
