"""Build a source-only online bootstrap package using Windows IExpress."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
stage = out / 'package'
stage.mkdir(exist_ok=True)
files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
files = sorted(set(filter(None, files)) | {p.relative_to(root).as_posix() for p in (root / 'installer').glob('*') if p.is_file()})
files = [p for p in files if p != 'SOURCE-MANIFEST.sha256']
for name in files:
    p = Path(name)
    if p.is_absolute() or '..' in p.parts or p.name in {'config.json', '.env'} or any(x in p.parts for x in ['.venv', '.git', '__pycache__']):
        raise RuntimeError(f'Forbidden payload file: {name}')
hashes = '\n'.join(f'{hashlib.sha256((root / p).read_bytes()).hexdigest()}  {p}' for p in files) + '\n'
(root / 'SOURCE-MANIFEST.sha256').write_bytes(hashes.encode('utf-8'))
files.append('SOURCE-MANIFEST.sha256')
with zipfile.ZipFile(stage / 'source.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for name in files:
        info = zipfile.ZipInfo(name, (2026, 10, 7, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, (root / name).read_bytes())
manifest = dict(version='0.2.0', source_sha256=hashlib.sha256((stage / 'source.zip').read_bytes()).hexdigest(),
    uv_url='https://github.com/astral-sh/uv/releases/download/0.12.23/uv-x86_64-pc-windows-msvc.zip',
    uv_sha256='75d05de6762778c31ee183398de7dd15093fad0ed90b1f236d8205ea5ec00c90')
(stage / 'payload.json').write_text(json.dumps(manifest, indent=2), encoding='ascii')
for name in ['install.ps1', 'uninstall.ps1', 'setup.cmd']:
    (stage / name).write_bytes((root / 'installer' / name).read_bytes())
for name in ['LICENSE', 'NOTICE']:
    (stage / name).write_bytes((root / name).read_bytes())
(stage / 'README.txt').write_bytes((root / 'installer' / 'README.md').read_bytes())
exe = out / 'JevAdvisorCommunity-0.2.0-online-setup.exe'
payloads = sorted(p.name for p in stage.iterdir() if p.is_file())
sed = '''[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=1
HideExtractAnimation=0
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=Install Jev Advisor Community? Internet access to GitHub and PyPI is required.
DisplayLicense=
FinishMessage=
TargetName={exe}
FriendlyName=Jev Advisor Community Online Setup
AppLaunched=cmd.exe /c setup.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles
[Strings]
{strings}
[SourceFiles]
SourceFiles0={stage}\\
[SourceFiles0]
{entries}
'''.format(exe=exe, stage=stage, strings='\n'.join(f'FILE{i}="{n}"' for i,n in enumerate(payloads)), entries='\n'.join(f'%FILE{i}%=' for i in range(len(payloads))))
sed_path = out / 'setup.sed'
sed_path.write_text(sed, encoding='ascii')
subprocess.run(['iexpress.exe', '/N', '/Q', str(sed_path)], check=True)
if not exe.is_file():
    raise RuntimeError('IExpress did not produce the installer')
with zipfile.ZipFile(out / 'JevAdvisorCommunity-0.2.0-online-setup.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for name in payloads:
        z.write(stage / name, f'JevAdvisorCommunity-Setup/{name}')
(out / 'JevAdvisorCommunity-0.2.0-source.zip').write_bytes((stage / 'source.zip').read_bytes())
artifacts = sorted([*out.glob('*.exe'), *out.glob('*.zip')])
(out / 'SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in artifacts), encoding='ascii')
print('\n'.join(str(p) for p in artifacts))
