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

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$sessionsPath = Join-Path $workspaceRoot "result\sessions.json"

function Get-SessionRecord {
  param(
    [string] $SessionName,
    [string] $Path
  )

  if (-not $SessionName -or -not (Test-Path -LiteralPath $Path)) {
    return $null
  }

  try {
    $content = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    if (-not $content) {
      return $null
    }

    $data = $content | ConvertFrom-Json
    if ($null -eq $data -or $null -eq $data.sessions) {
      return $null
    }

    foreach ($session in $data.sessions) {
      if ($session.session_name -eq $SessionName) {
        return $session
      }
    }
  } catch {
    [Console]::Error.WriteLine("[browser-use-utf8] Unable to parse sessions file '$Path': $($_.Exception.Message)")
  }

  return $null
}

function Test-AttachCompleted {
  param($SessionRecord)

  if ($null -eq $SessionRecord) {
    return $false
  }

  $hasAttachCompleted = $SessionRecord.PSObject.Properties.Name -contains "attach_completed"
  if ($hasAttachCompleted) {
    return [bool]$SessionRecord.attach_completed
  }

  return (
    ($SessionRecord.PSObject.Properties.Name -contains "cdp_url") -and
    [string]::IsNullOrWhiteSpace([string]$SessionRecord.cdp_url) -eq $false -and
    (($SessionRecord.PSObject.Properties.Name -notcontains "status") -or $SessionRecord.status -ne "closed")
  )
}

function Resolve-AttachMode {
  param(
    [string] $ExplicitAttachMode,
    [bool] $HasCdpUrl,
    $SessionRecord
  )

  if ($ExplicitAttachMode) {
    return $ExplicitAttachMode
  }

  if ($HasCdpUrl) {
    if (Test-AttachCompleted -SessionRecord $SessionRecord) {
      return "reuse"
    }

    return "bootstrap"
  }

  return "reuse"
}

function Get-CommandIndex {
  param(
    [string[]] $Args
  )

  $index = 0

  while ($index -lt $Args.Length) {
    $token = $Args[$index]

    switch ($token) {
      "--session" {
        $index += 2
        continue
      }
      "--cdp-url" {
        $index += 2
        continue
      }
      "--attach-mode" {
        $index += 2
        continue
      }
      "--json" {
        $index += 1
        continue
      }
      default {
        if ($token.StartsWith("--")) {
          $index += 1
          continue
        }

        return $index
      }
    }
  }

  return $Args.Length
}

function Split-GlobalAndCommandArgs {
  param(
    [System.Collections.Generic.List[string]] $Args
  )

  $globalArgs = [System.Collections.Generic.List[string]]::new()
  $commandArgs = [System.Collections.Generic.List[string]]::new()
  $index = 0

  while ($index -lt $Args.Count) {
    $token = $Args[$index]

    switch ($token) {
      "--session" {
        $globalArgs.Add($token)
        if ($index + 1 -lt $Args.Count) {
          $globalArgs.Add($Args[$index + 1])
        }
        $index += 2
        continue
      }
      "--cdp-url" {
        $globalArgs.Add($token)
        if ($index + 1 -lt $Args.Count) {
          $globalArgs.Add($Args[$index + 1])
        }
        $index += 2
        continue
      }
      "--attach-mode" {
        $globalArgs.Add($token)
        if ($index + 1 -lt $Args.Count) {
          $globalArgs.Add($Args[$index + 1])
        }
        $index += 2
        continue
      }
      "--json" {
        $index += 1
        continue
      }
      default {
        if ($token.StartsWith("--")) {
          $globalArgs.Add($token)
          $index += 1
          continue
        }

        for ($remaining = $index; $remaining -lt $Args.Count; $remaining++) {
          $commandArgs.Add($Args[$remaining])
        }

        break
      }
    }
  }

  return [pscustomobject]@{
    GlobalArgs = $globalArgs
    CommandArgs = $commandArgs
  }
}

$sessionName = $null
$cdpUrl = $null
$explicitAttachMode = $null
$jsonIndices = [System.Collections.Generic.List[int]]::new()

for ($i = 0; $i -lt $BrowserUseArgs.Length; $i++) {
  $arg = $BrowserUseArgs[$i]

  switch ($arg) {
    "--session" {
      if ($i + 1 -lt $BrowserUseArgs.Length) {
        $sessionName = $BrowserUseArgs[$i + 1]
        $i++
      }
      continue
    }
    "--cdp-url" {
      if ($i + 1 -lt $BrowserUseArgs.Length) {
        $cdpUrl = $BrowserUseArgs[$i + 1]
        $i++
      }
      continue
    }
    "--attach-mode" {
      if ($i + 1 -lt $BrowserUseArgs.Length) {
        $explicitAttachMode = $BrowserUseArgs[$i + 1]
        $i++
      }
      continue
    }
    "--json" {
      $jsonIndices.Add($i)
      continue
    }
  }
}

$sessionRecord = Get-SessionRecord -SessionName $sessionName -Path $sessionsPath
$attachMode = Resolve-AttachMode -ExplicitAttachMode $explicitAttachMode -HasCdpUrl ([string]::IsNullOrWhiteSpace($cdpUrl) -eq $false) -SessionRecord $sessionRecord
$validAttachModes = @("bootstrap", "reuse", "repair")

if ($attachMode -notin $validAttachModes) {
  [Console]::Error.WriteLine("[browser-use-utf8] Invalid --attach-mode '$attachMode'. Valid values: bootstrap, reuse, repair.")
  exit 64
}

$normalizedArgs = [System.Collections.Generic.List[string]]::new()
$hadJson = $jsonIndices.Count -gt 0
$originalCommandIndex = Get-CommandIndex -Args $BrowserUseArgs
$jsonWasMisplaced = $false

foreach ($jsonIndex in $jsonIndices) {
  if ($jsonIndex -ge $originalCommandIndex) {
    $jsonWasMisplaced = $true
    break
  }
}

for ($i = 0; $i -lt $BrowserUseArgs.Length; $i++) {
  $arg = $BrowserUseArgs[$i]

  if ($arg -eq "--json") {
    continue
  }

  if ($arg -eq "--attach-mode") {
    $i++
    continue
  }

  if ($arg -eq "--cdp-url") {
    if ($i + 1 -lt $BrowserUseArgs.Length) {
      if ($attachMode -eq "reuse") {
        if ($sessionName) {
          [Console]::Error.WriteLine("[browser-use-utf8] Session '$sessionName' is in reuse mode; ignoring --cdp-url.")
        } else {
          [Console]::Error.WriteLine("[browser-use-utf8] Reuse mode active; ignoring --cdp-url.")
        }
      } else {
        $normalizedArgs.Add($arg)
        $normalizedArgs.Add($BrowserUseArgs[$i + 1])
      }

      $i++
      continue
    }
  }

  $normalizedArgs.Add($arg)
}

if ($hadJson) {
  $splitArgs = Split-GlobalAndCommandArgs -Args $normalizedArgs
  $reorderedArgs = [System.Collections.Generic.List[string]]::new()

  foreach ($token in $splitArgs.GlobalArgs) {
    $reorderedArgs.Add($token)
  }

  $reorderedArgs.Add("--json")

  foreach ($token in $splitArgs.CommandArgs) {
    $reorderedArgs.Add($token)
  }

  $normalizedArgs = $reorderedArgs

  if ($jsonWasMisplaced) {
    [Console]::Error.WriteLine("[browser-use-utf8] Normalized trailing --json to the browser-use global flag position.")
  } elseif ($jsonIndices.Count -gt 1) {
    [Console]::Error.WriteLine("[browser-use-utf8] Collapsed duplicate --json flags into a single global flag.")
  }
}

if (($attachMode -eq "bootstrap" -or $attachMode -eq "repair") -and [string]::IsNullOrWhiteSpace($cdpUrl)) {
  [Console]::Error.WriteLine("[browser-use-utf8] Attach mode '$attachMode' was requested without --cdp-url; continuing with session-only command.")
}

& browser-use @normalizedArgs
exit $LASTEXITCODE
