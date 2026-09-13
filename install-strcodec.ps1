<#
.SYNOPSIS
  Install or update strcodec (SPSS Modeler .str <-> Jython codec for coding agents) into a workspace.

.DESCRIPTION
  One-shot installer, in the spirit of spss-clemb-mcp's install script.

    irm https://raw.githubusercontent.com/YokeSin/strcodec/main/install-strcodec.ps1 | iex
    .\install-strcodec.ps1 [-Workspace <dir>] [-Source <local clone>] [-Ref main] [-NoHooks] [-NoAgentsMd]

  What it does (idempotent; safe to re-run to update):
    1. Gets the strcodec files: from -Source (a local clone), from the clone this script sits in,
       or by downloading the GitHub zip archive (no git needed).
    2. Copies .bob/strcodec/ and .bob/skills/{spss-str-decode,spss-str-rebuild,_shared} into <workspace>/.bob/.
       Keeps your python.path, logs/ and the non-version keys of config.json.
    3. Merges the three strcodec hooks into <workspace>/.bob/settings.json (existing hooks are kept;
       a backup settings.json.bak-<timestamp> is written before changing it).
    4. Creates AGENTS.md, or appends the strcodec section to an existing one (once).
    5. Appends strcodec's ignore patterns to .gitignore when the workspace is a git repo.
    6. Checks that spss-clemb-mcp / ibm-docs-mcp are registered in ~/.bob/settings/mcp.json and points to
       their repositories if not (they are installed separately).
    7. Runs strcodec.cmd python-info and status to verify.

  Environment overrides (useful with `irm | iex`, which cannot take parameters):
    STRCODEC_WORKSPACE  target workspace (default: current directory)
    STRCODEC_REF        git ref to download (default: main)
    STRCODEC_SOURCE     local clone to install from instead of downloading
#>
[CmdletBinding()]
param(
    [string]$Workspace = $(if ($env:STRCODEC_WORKSPACE) { $env:STRCODEC_WORKSPACE } else { (Get-Location).Path }),
    [string]$Source = $env:STRCODEC_SOURCE,
    [string]$Ref = $(if ($env:STRCODEC_REF) { $env:STRCODEC_REF } else { "main" }),
    [string]$Repo = "https://github.com/YokeSin/strcodec",
    [switch]$NoHooks,
    [switch]$NoAgentsMd
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"

function Info($msg) { Write-Host "[strcodec] $msg" }
function Ok($msg) { Write-Host "[strcodec] OK   $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[strcodec] WARN $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "[strcodec] FAIL $msg" -ForegroundColor Red; exit 1 }
function ReadText($p) { [System.IO.File]::ReadAllText($p, [System.Text.Encoding]::UTF8) }
function WriteText($p, $t) { [System.IO.File]::WriteAllText($p, $t, $Utf8NoBom) }

# ---------------------------------------------------------------- 1. locate the source files
function Get-SourceDir {
    if ($Source) {
        $s = (Resolve-Path $Source).Path
        if (-not (Test-Path (Join-Path $s ".bob\strcodec\strcodec.py"))) { Fail "-Source does not look like a strcodec checkout: $s" }
        Info "source: local checkout $s"
        return $s
    }
    if ($PSCommandPath) {
        $here = Split-Path -Parent $PSCommandPath
        if (Test-Path (Join-Path $here ".bob\strcodec\strcodec.py")) {
            Info "source: the checkout this script is in ($here)"
            return $here
        }
    }
    $zipUrl = "$Repo/archive/refs/heads/$Ref.zip"
    $tmp = Join-Path $env:TEMP ("strcodec-install-" + $Stamp)
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    $zip = Join-Path $tmp "strcodec.zip"
    Info "downloading $zipUrl"
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $zipUrl -OutFile $zip -UseBasicParsing
    } catch {
        Fail "download failed: $($_.Exception.Message)`n         Clone the repository yourself and run:  .\install-strcodec.ps1 -Source <clone dir> -Workspace <workspace>"
    }
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $inner = Get-ChildItem -Path $tmp -Directory | Where-Object { Test-Path (Join-Path $_.FullName ".bob\strcodec\strcodec.py") } | Select-Object -First 1
    if (-not $inner) { Fail "the archive does not contain .bob/strcodec" }
    return $inner.FullName
}

# ---------------------------------------------------------------- 2. copy the tool and the skills
function Copy-Tree($from, $to, [string[]]$exclude) {
    New-Item -ItemType Directory -Path $to -Force | Out-Null
    Get-ChildItem -Path $from -Recurse -Force | ForEach-Object {
        $rel = $_.FullName.Substring($from.Length).TrimStart("\")
        $top = $rel.Split("\")[0]
        if ($exclude -contains $top -or $_.Name -eq "__pycache__" -or $_.FullName -match "\\__pycache__\\" -or $_.Extension -eq ".pyc") { return }
        $dest = Join-Path $to $rel
        if ($_.PSIsContainer) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
        else { Copy-Item -Path $_.FullName -Destination $dest -Force }
    }
}

function Merge-Config($newPath, $oldPath) {
    # keep the user's settings (clemb_path, ignore_dirs, ...) but always take the new tool_version
    if (-not (Test-Path $oldPath)) { return }
    try {
        $new = ReadText $newPath | ConvertFrom-Json
        $old = ReadText $oldPath | ConvertFrom-Json
    } catch { Warn "config.json could not be parsed; the new default is installed (old one kept as config.json.bak-$Stamp)"; Copy-Item $oldPath "$oldPath.bak-$Stamp"; return }
    $changed = @()
    foreach ($p in $old.PSObject.Properties) {
        if ($p.Name -eq "tool_version") { continue }
        $cur = $new.PSObject.Properties[$p.Name]
        if ($null -eq $cur) { $new | Add-Member -NotePropertyName $p.Name -NotePropertyValue $p.Value; $changed += $p.Name }
        elseif (($cur.Value | ConvertTo-Json -Compress -Depth 5) -ne ($p.Value | ConvertTo-Json -Compress -Depth 5)) { $cur.Value = $p.Value; $changed += $p.Name }
    }
    if ($changed.Count) { Info "config.json: kept your values for $($changed -join ', ')" }
    WriteText $newPath (($new | ConvertTo-Json -Depth 10) + "`n")
}

function Install-Files($src, $ws) {
    $bob = Join-Path $ws ".bob"
    $toolDst = Join-Path $bob "strcodec"
    $toolSrc = Join-Path $src ".bob\strcodec"
    $keepPythonPath = $null
    $oldConfig = $null
    if (Test-Path $toolDst) {
        $pp = Join-Path $toolDst "python.path"
        if (Test-Path $pp) { $keepPythonPath = ReadText $pp }
        $cf = Join-Path $toolDst "config.json"
        if (Test-Path $cf) { $oldConfig = Join-Path $env:TEMP ("strcodec-config-" + $Stamp + ".json"); Copy-Item $cf $oldConfig }
        $oldVer = ""
        try { $oldVer = (ReadText $cf | ConvertFrom-Json).tool_version } catch {}
        Info "updating existing .bob/strcodec (was tool_version $oldVer)"
        Get-ChildItem -Path $toolDst -Force | Where-Object { $_.Name -notin @("logs", "python.path") } | Remove-Item -Recurse -Force
    }
    Copy-Tree $toolSrc $toolDst @("logs", "python.path", "__pycache__")
    if ($keepPythonPath) { WriteText (Join-Path $toolDst "python.path") $keepPythonPath }
    if ($oldConfig) { Merge-Config (Join-Path $toolDst "config.json") $oldConfig; Remove-Item $oldConfig -Force }
    $ver = (ReadText (Join-Path $toolDst "config.json") | ConvertFrom-Json).tool_version
    Ok ".bob/strcodec installed (tool_version $ver)"

    foreach ($skill in @("spss-str-decode", "spss-str-rebuild", "_shared")) {
        $s = Join-Path $src ".bob\skills\$skill"
        if (-not (Test-Path $s)) { Warn "skill missing in source: $skill"; continue }
        Copy-Tree $s (Join-Path $bob "skills\$skill") @()
    }
    Ok ".bob/skills/spss-str-decode, spss-str-rebuild, _shared installed"
}

# ---------------------------------------------------------------- 3. hooks
function Merge-Hooks($src, $ws) {
    $dst = Join-Path $ws ".bob\settings.json"
    $ours = ReadText (Join-Path $src ".bob\settings.json") | ConvertFrom-Json
    if (-not (Test-Path $dst)) {
        Copy-Item (Join-Path $src ".bob\settings.json") $dst
        Ok ".bob/settings.json created with the 3 strcodec hooks"
        return
    }
    try { $cur = ReadText $dst | ConvertFrom-Json } catch { Fail ".bob/settings.json is not valid JSON; fix it or merge the hooks by hand (see README)" }
    if (-not $cur.PSObject.Properties["hooks"]) { $cur | Add-Member -NotePropertyName hooks -NotePropertyValue ([pscustomobject]@{}) }
    $added = @()
    foreach ($ev in $ours.hooks.PSObject.Properties) {
        $name = $ev.Name
        $existing = @()
        if ($cur.hooks.PSObject.Properties[$name]) { $existing = @($cur.hooks.$name) }
        $has = $false
        foreach ($entry in $existing) { foreach ($h in @($entry.hooks)) { if ("$($h.command)" -match "strcodec\.cmd hook") { $has = $true } } }
        if ($has) { continue }
        $merged = $existing + @($ev.Value)
        if ($cur.hooks.PSObject.Properties[$name]) { $cur.hooks.$name = $merged } else { $cur.hooks | Add-Member -NotePropertyName $name -NotePropertyValue $merged }
        $added += $name
    }
    if (-not $added.Count) { Ok ".bob/settings.json already has the strcodec hooks"; return }
    Copy-Item $dst "$dst.bak-$Stamp"
    WriteText $dst (($cur | ConvertTo-Json -Depth 20) + "`n")
    Ok ".bob/settings.json: added hooks for $($added -join ', ') (backup: settings.json.bak-$Stamp)"
}

# ---------------------------------------------------------------- 4. AGENTS.md
function Install-AgentsMd($src, $ws) {
    $s = Join-Path $src "AGENTS.md"
    $d = Join-Path $ws "AGENTS.md"
    if (-not (Test-Path $s)) { Warn "AGENTS.md missing in source"; return }
    if (-not (Test-Path $d)) { Copy-Item $s $d; Ok "AGENTS.md created"; return }
    $cur = ReadText $d
    if ($cur.Contains("strcodec.cmd") -or $cur.Contains(".bob/strcodec")) { Ok "AGENTS.md already mentions strcodec (left unchanged)"; return }
    $body = (ReadText $s) -replace "^# [^\r\n]*\r?\n", ""   # drop the source's top-level title
    WriteText $d ($cur.TrimEnd() + "`n`n---`n`n" + $body.TrimStart())
    Ok "AGENTS.md: appended the strcodec section"
}

# ---------------------------------------------------------------- 5. .gitignore
function Update-GitIgnore($ws) {
    $gi = Join-Path $ws ".gitignore"
    if (-not (Test-Path (Join-Path $ws ".git")) -and -not (Test-Path $gi)) { return }
    $lines = @("*.strcode/", "*_rebuilt.str", ".bob/strcodec/logs/", ".bob/strcodec/python.path", "__pycache__/")
    $cur = if (Test-Path $gi) { ReadText $gi } else { "" }
    $have = $cur -split "\r?\n" | ForEach-Object { $_.Trim() }
    $missing = $lines | Where-Object { $have -notcontains $_ }
    if (-not $missing.Count) { Ok ".gitignore already covers strcodec artifacts"; return }
    $add = "# strcodec: decoded sidecars, rebuilt streams, logs, personal python setting`n" + ($missing -join "`n") + "`n"
    $head = ""
    if ($cur) { $head = $cur.TrimEnd() + "`n`n" }
    WriteText $gi ($head + $add)
    Ok ".gitignore: added $($missing -join ', ')"
}

# ---------------------------------------------------------------- 6. MCP servers (installed separately)
function Check-Mcp($ws) {
    # MCP servers are installed separately; here we only report whether Bob knows them (global or workspace config)
    $found = @{}
    foreach ($cfg in @((Join-Path $env:USERPROFILE ".bob\settings\mcp.json"), (Join-Path $ws ".bob\mcp.json"))) {
        if (-not (Test-Path $cfg)) { continue }
        try { foreach ($n in ((ReadText $cfg) | ConvertFrom-Json).mcpServers.PSObject.Properties.Name) { $found[$n] = $cfg } } catch {}
    }
    foreach ($m in @(@{n = "spss-clemb-mcp"; u = "https://github.com/hkwd/spss-clemb-mcp"; why = "runs the rebuild scripts (execute_clemb)"},
                     @{n = "ibm-docs-mcp"; u = "https://github.com/hkwd/ibm-docs-mcp"; why = "looks up node properties in IBM Docs"})) {
        if ($found.ContainsKey($m.n)) { Ok "MCP $($m.n) is registered ($($found[$m.n]))" }
        else { Warn "MCP $($m.n) is not registered ($($m.why)). Install it from $($m.u)" }
    }
}

# ---------------------------------------------------------------- 7. verify
function Verify($ws) {
    $cmd = Join-Path $ws ".bob\strcodec\strcodec.cmd"
    Info "python-info:"
    & cmd.exe /c "`"$cmd`" python-info" 2>&1 | ForEach-Object { Write-Host "    $_" }
    if ($LASTEXITCODE -ne 0) { Warn "no usable CPython 3.10+ found. Install Python 3.10+ (the one spss-clemb-mcp uses is fine) or set STRCODEC_PYTHON"; return }
    Info "status:"
    & cmd.exe /c "`"$cmd`" status" 2>&1 | ForEach-Object { Write-Host "    $_" }
    if ($LASTEXITCODE -ne 0) { Warn "strcodec.cmd status failed; see .bob/strcodec/logs/" }
}

# ---------------------------------------------------------------- main
$Workspace = (Resolve-Path $Workspace).Path
Info "workspace: $Workspace"
$src = Get-SourceDir
Install-Files $src $Workspace
if ($NoHooks) { Info "hooks skipped (-NoHooks)" } else { Merge-Hooks $src $Workspace }
if ($NoAgentsMd) { Info "AGENTS.md skipped (-NoAgentsMd)" } else { Install-AgentsMd $src $Workspace }
Update-GitIgnore $Workspace
Check-Mcp $Workspace
Verify $Workspace
Write-Host ""
Ok "done. Next: open the workspace in Bob and mention a stream file, e.g. '@your_stream.str' plus a question about it"
Info "manual steps and options: see README.md in $Repo"
