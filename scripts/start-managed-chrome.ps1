param(
  [Parameter(Mandatory = $true)]
  [int] $CdpPort,

  [Parameter(Mandatory = $true)]
  [string] $UserDataDir,

  [Parameter(Mandatory = $true)]
  [string] $ProxyServer,

  [string] $StartUrl,

  [string] $ChromePath
)

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $utf8NoBom
[Console]::InputEncoding = $utf8NoBom
[System.Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

function Resolve-ChromePath {
  param(
    [string] $ExplicitPath
  )

  if ($ExplicitPath) {
    return $ExplicitPath
  }

  $candidates = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
  )

  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) {
      return $candidate
    }
  }

  throw "Unable to locate chrome.exe. Pass -ChromePath explicitly."
}

$resolvedChromePath = Resolve-ChromePath -ExplicitPath $ChromePath

if (-not (Test-Path -LiteralPath $UserDataDir)) {
  New-Item -ItemType Directory -Path $UserDataDir -Force | Out-Null
}

$argumentList = [System.Collections.Generic.List[string]]::new()
$argumentList.Add("--remote-debugging-port=$CdpPort")
$argumentList.Add("--user-data-dir=$UserDataDir")
$argumentList.Add("--proxy-server=$ProxyServer")
$argumentList.Add("--no-first-run")
$argumentList.Add("--no-default-browser-check")

if (-not [string]::IsNullOrWhiteSpace($StartUrl)) {
  $argumentList.Add($StartUrl)
}

$process = Start-Process -FilePath $resolvedChromePath -ArgumentList $argumentList -PassThru

[pscustomobject]@{
  chrome_path = $resolvedChromePath
  chrome_pid = $process.Id
  cdp_port = $CdpPort
  cdp_url = "http://127.0.0.1:$CdpPort"
  user_data_dir = $UserDataDir
  proxy_server = $ProxyServer
  start_url = $StartUrl
  arguments = $argumentList
} | ConvertTo-Json -Depth 4 -Compress
