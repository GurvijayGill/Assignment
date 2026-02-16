param(
    [switch]$Install
)

Set-Location -Path $PSScriptRoot

if ($Install) {
    python -m pip install -r requirements.txt
}

python -m pytest -q -p no:cacheprovider
