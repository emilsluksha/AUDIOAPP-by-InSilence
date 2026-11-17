"""Package the complete PyInstaller onedir application as a portable Windows ZIP."""
from pathlib import Path
import hashlib
import zipfile

root = Path(__file__).resolve().parent.parent
folder = root/'dist'/'KEYWAVE'
executable = folder/'KEYWAVE.exe'
if not executable.is_file():
    raise SystemExit('Build the KEYWAVE folder before packaging')

destination = root/'dist'/'KEYWAVE-Windows-x64-folder.zip'
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
    for file in sorted(folder.rglob('*')):
        if file.is_file():
            archive.write(file, Path('KEYWAVE')/file.relative_to(folder))
    for name in ('README.md', 'VERIFICATION.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md'):
        archive.write(root/name,name)
with destination.open('rb') as stream:
    digest = hashlib.file_digest(stream,'sha256').hexdigest()
destination.with_suffix('.zip.sha256').write_text(f'{digest}  {destination.name}\n',encoding='ascii')
print(f'{destination.name}: {destination.stat().st_size / 1024**2:.1f} MiB; SHA256 {digest}')
