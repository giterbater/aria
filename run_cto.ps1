$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = $scriptDir
$env:NVIDIA_API_KEY = $env:NVIDIA_API_KEY  # preserve existing env var

& "C:\Users\nevaan kaul\AppData\Local\Programs\Python\Python310\python.exe" -m cto --repo $scriptDir @args
