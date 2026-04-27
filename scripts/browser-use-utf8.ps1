param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $BrowserUseArgs
)

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $utf8NoBom
[Console]::InputEncoding = $utf8NoBom
[System.Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

& browser-use @BrowserUseArgs
exit $LASTEXITCODE
