$ErrorActionPreference = 'Stop'
& "$PSScriptRoot\.venv-ram\Scripts\python.exe" "$PSScriptRoot\detect.py" @args
exit $LASTEXITCODE
