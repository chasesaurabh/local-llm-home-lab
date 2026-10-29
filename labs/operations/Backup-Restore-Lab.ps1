# Windows reader recovery lab. Self-contained archive worker; no external Python install required.
# Plan performs no service query. Backup/Restore require explicit execution gates.
[CmdletBinding()]
param(
    [ValidateSet('Plan','Backup','Restore')][string]$Mode = 'Plan',
    [string]$LabRoot = (Join-Path $env:USERPROFILE 'local-llm-lab'),
    [switch]$Execute,
    [switch]$ExclusiveLabWindow,
    [string]$PrivateDirectory,
    [string]$EnvFile,
    [ValidatePattern('^local-llm-[a-z0-9-]+$')][string]$SourceName = 'local-llm-l03-001',
    [ValidatePattern('^local-llm-[a-z0-9-]+$')][string]$SourceVolume = 'local-llm-l03-001-data',
    [ValidateRange(3103,3199)][int]$SourcePort = 3103,
    [ValidatePattern('^local-llm-l06-[a-z0-9-]+$')][string]$RestoreName = 'local-llm-l06-001',
    [ValidateRange(3106,3199)][int]$RestorePort = 3106
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Image = 'ghcr.io/open-webui/open-webui@sha256:a5b9e403d19154796850679c8c5d1295301cee954be8b84ddd62af92426558f7'
$LabRoot = [IO.Path]::GetFullPath($LabRoot)
$PrivateRoot = Join-Path $LabRoot 'recovery'
if ([string]::IsNullOrWhiteSpace($PrivateDirectory)) { $PrivateDirectory = Join-Path $PrivateRoot 'l06-backup-001' }
if ([string]::IsNullOrWhiteSpace($EnvFile)) { $EnvFile = Join-Path $LabRoot 'webui\webui.env' }
if ($SourceName -eq $RestoreName -or $SourceVolume -eq ($RestoreName + '-data') -or $SourcePort -eq $RestorePort) {
    throw 'Source and restore names, volumes and ports must remain separate.'
}
$WorkerText = @'
"""Container-side archive worker. Coordinator invokes only with owned, quiesced volume.
No network, package installation, inference, secret printing, or database writes.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sqlite3
import tarfile

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def safe_members(archive):
    members = archive.getmembers()
    for member in members:
        name = PurePosixPath(member.name)
        if name.is_absolute() or ".." in name.parts or "\\" in member.name:
            raise ValueError("archive path escapes destination")
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise ValueError("special file rejected")
        if member.issym() or member.islnk():
            target = PurePosixPath(member.linkname)
            if target.is_absolute() or "\\" in member.linkname:
                raise ValueError("absolute link rejected")
            # Permit relative Hugging Face cache links only if their normalized target remains inside.
            parts = list(name.parent.parts) if member.issym() else []
            for component in target.parts:
                if component == "..":
                    if not parts:
                        raise ValueError("link escapes archive root")
                    parts.pop()
                elif component != ".":
                    parts.append(component)
    return members

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["backup", "restore", "check"])
    args = parser.parse_args()
    data = Path("/lab-data")
    archive_path = Path("/lab-backup/data.tar.gz")
    if args.action == "backup":
        if archive_path.exists():
            raise RuntimeError("refusing to overwrite archive")
        if not (data / "webui.db").is_file():
            raise RuntimeError("expected application database absent")
        # The complete volume includes uploads, vector data, caches and SQLite sidecars if present.
        with tarfile.open(archive_path, "x:gz", dereference=False) as archive:
            for child in sorted(data.iterdir()):
                archive.add(child, arcname=child.name, recursive=True)
        with tarfile.open(archive_path, "r:gz") as archive:
            count = len(safe_members(archive))
        print(json.dumps({"action": "archive_created", "sha256": digest(archive_path),
                          "bytes": archive_path.stat().st_size, "members": count}))
    elif args.action == "restore":
        if any(data.iterdir()):
            raise RuntimeError("restore target is not empty")
        with tarfile.open(archive_path, "r:gz") as archive:
            members = safe_members(archive)
            # Python's data filter adds traversal/link/permission defenses. Require supported runtime.
            if not hasattr(tarfile, "data_filter"):
                raise RuntimeError("Python tar data filter unavailable; do not weaken extraction")
            archive.extractall(data, members=members, filter="data")
        print(json.dumps({"action": "archive_extracted", "members": len(members)}))
    else:
        db = data / "webui.db"
        if not db.is_file():
            raise RuntimeError("restored database missing")
        # Quiesced restored copy only. Read-only mode; no table content or account data output.
        with sqlite3.connect("file:" + str(db) + "?mode=ro", uri=True) as con:
            result = con.execute("PRAGMA quick_check").fetchall()
        ok = result == [("ok",)]
        if not ok:
            raise RuntimeError("restored SQLite quick_check failed")
        print(json.dumps({"sqlite_quick_check": "ok", "database_bytes": db.stat().st_size,
                          "database_sha256_before_app_start": digest(db),
                          "uploads_directory_exists": (data / "uploads").is_dir(),
                          "vector_directory_exists": (data / "vector_db").is_dir(),
                          "application_restoration_pass": None}))

if __name__ == "__main__":
    main()

'@

function Invoke-LabDocker([string[]]$Arguments) {
    $output = & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker operation failed: $($Arguments[0])" }
    return $output
}
function Private-Path([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { throw 'Supply an explicit private directory.' }
    $full = [IO.Path]::GetFullPath($Path)
    $prefix = [IO.Path]::GetFullPath($PrivateRoot).TrimEnd('\') + '\'
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Private directory must be a strict descendant of the selected LabRoot recovery folder.'
    }
    if ((Split-Path -Leaf $full) -notmatch '^l06-backup-[a-zA-Z0-9-]+$') {
        throw 'Private directory name must start l06-backup- and use letters, numbers or hyphens.'
    }
    if ($full.Contains(',')) { throw 'Comma in Docker bind path is not supported.' }
    # Reject reparse points in every existing component to prevent junction escape.
    $cursor = $full
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse path rejected.' }
        }
        $parent = Split-Path -Parent $cursor
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
    return $full
}
function Protect-Directory([string]$Path) {
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($principal in @($sid, 'S-1-5-18', 'S-1-5-32-544')) {
        $identity = New-Object Security.Principal.SecurityIdentifier($principal)
        $rule = New-Object Security.AccessControl.FileSystemAccessRule(
            $identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}
function Save-PrivateJson([string]$Path, $Value) {
    $Value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $Path -Encoding UTF8
}
function Selected-Container([string]$Name) {
    # Never print Config.Env or whole inspect output.
    $format = '{"id":{{json .Id}},"image":{{json .Image}},"image_ref":{{json .Config.Image}},"state":{{json .State.Status}},"running":{{json .State.Running}},"mounts":{{json .Mounts}},"ports":{{json .HostConfig.PortBindings}}}'
    return ((Invoke-LabDocker @('inspect','--format',$format,$Name)) -join "`n" | ConvertFrom-Json)
}
function Wait-Health([int]$Port) {
    $limit = [DateTime]::UtcNow.AddMinutes(10)
    while ([DateTime]::UtcNow -lt $limit) {
        try {
            $reply = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 5
            if ($reply.StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Seconds 3
    }
    throw 'Health endpoint did not become ready; preserve instance and diagnose.'
}
function Run-Worker([string]$Action, [string]$Volume, [string]$Private, [switch]$ReadOnlyData) {
    $dataMount = "type=volume,src=$Volume,dst=/lab-data,volume-nocopy"
    if ($ReadOnlyData) { $dataMount += ',readonly' }
    $backupMount = "type=bind,src=$Private,dst=/lab-backup"
    if ($Action -ne 'backup') { $backupMount += ',readonly' }
    $arguments = @('run','--rm','-i','--pull','never','--network','none',
        '--mount',$dataMount,'--mount',$backupMount,
        '--entrypoint','python',$Image,'-',$Action)
    $workerOutput = $WorkerText | & docker @arguments
    if ($LASTEXITCODE -ne 0) { throw "Archive worker failed during $Action." }
    return ($workerOutput -join "`n" | ConvertFrom-Json)
}

if ($Mode -eq 'Plan') {
    [PSCustomObject]@{ Mode='plan-only'; Source=$SourceName; Volume=$SourceVolume;
        Image=$Image; RestoreName=$RestoreName; RestorePort=$RestorePort;
        LabRoot=$LabRoot; PrivateDirectory=$PrivateDirectory; EnvFile=$EnvFile; SourcePort=$SourcePort; State='No service query or mutation in Plan mode.' } | ConvertTo-Json
    return
}
if (-not $Execute -or -not $ExclusiveLabWindow) {
    throw 'Execution requires both -Execute and -ExclusiveLabWindow after coordinator review.'
}
$Private = Private-Path $PrivateDirectory
if (-not (Test-Path -LiteralPath $LabRoot -PathType Container)) { throw 'Existing Chapter 14/15 LabRoot folder required.' }
if ((Invoke-LabDocker @('context','show')) -ne 'desktop-linux') { throw 'Unexpected Docker context.' }
$cached = Invoke-LabDocker @('image','inspect','--format','{{.Id}}',$Image)
if (-not $cached) { throw 'Pinned image is not cached; this script never pulls.' }
Add-Type -AssemblyName System.Security

if ($Mode -eq 'Backup') {
    if (Test-Path -LiteralPath $Private) { throw 'Backup directory exists; select a new attempt.' }
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) { throw 'Protected existing env file required.' }
    $envFull = [IO.Path]::GetFullPath($EnvFile)
    if (-not $envFull.StartsWith(($LabRoot.TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Env file must be inside the selected LabRoot, normally webui/webui.env.'
    }
    $envCursor = $envFull
    while ($envCursor) {
        if (Test-Path -LiteralPath $envCursor) {
            if ((Get-Item -LiteralPath $envCursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Secret reparse path rejected.' }
        }
        $parent = Split-Path -Parent $envCursor
        if ($parent -eq $envCursor) { break }
        $envCursor = $parent
    }
    $source = Selected-Container $SourceName
    $mount = @($source.mounts | Where-Object { $_.Type -eq 'volume' -and $_.Name -eq $SourceVolume -and $_.Destination -eq '/app/backend/data' })
    if ($mount.Count -ne 1 -or $source.image -ne $cached) { throw 'Source image or named volume differs from reviewed lab.' }
    $bindings = @($source.ports.'8080/tcp')
    if ($bindings.Count -ne 1 -or $bindings[0].HostIp -ne '127.0.0.1' -or [int]$bindings[0].HostPort -ne $SourcePort) {
        throw 'Source container does not match the expected loopback UI port.'
    }
    $runningUsers = @(Invoke-LabDocker @('ps','--filter',"volume=$SourceVolume",'--format','{{.Names}}'))
    if (@($runningUsers | Where-Object { $_ -and $_ -ne $SourceName }).Count -ne 0) { throw 'Another running container uses source volume.' }
    New-Item -ItemType Directory -Path $Private | Out-Null
    Protect-Directory $Private
    # DPAPI protects the key copy for this Windows user/profile. It is not portable key recovery.
    $secret = [IO.File]::ReadAllBytes($envFull)
    try {
        $sealed = [Security.Cryptography.ProtectedData]::Protect($secret, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
        [IO.File]::WriteAllBytes((Join-Path $Private 'secret-env.dpapi'), $sealed)
    } finally { if ($secret) { [Array]::Clear($secret, 0, $secret.Length) } }
    $record = [ordered]@{ Status='started'; StartedUtc=[DateTime]::UtcNow.ToString('o');
        Source=$SourceName; SourceId=$source.id; SourceVolume=$SourceVolume; SourcePort=$SourcePort;
        Image=$Image; ImageId=$source.image; WasRunning=[bool]$source.running;
        ArchiveProtection='restricted NTFS ACL; not independently encrypted';
        SecretProtection='DPAPI CurrentUser; requires same recoverable Windows profile';
        ApplicationRestoreVerified=$false }
    try {
        if ($source.running) { Invoke-LabDocker @('stop','--time','60',$SourceName) | Out-Null }
        $after = Selected-Container $SourceName
        if ($after.running -or $after.state -ne 'exited') { throw 'Source is not quiesced.' }
        $stillRunning = @(Invoke-LabDocker @('ps','--filter',"volume=$SourceVolume",'--format','{{.Names}}'))
        if (@($stillRunning | Where-Object { $_ }).Count) { throw 'Volume still has a running user.' }
        $record.QuiescedUtc = [DateTime]::UtcNow.ToString('o')
        $record.Archive = Run-Worker 'backup' $SourceVolume $Private -ReadOnlyData
        $actual = (Get-FileHash -LiteralPath (Join-Path $Private 'data.tar.gz') -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $record.Archive.sha256) { throw 'Host/archive hash disagreement.' }
        $record.Status = 'archive-created-restore-pending'
    } catch {
        $record.Status = 'backup-failed'
        $record.FailureType = $_.Exception.GetType().Name
        throw
    } finally {
        if ($source.running) {
            try {
                Invoke-LabDocker @('start',$SourceName) | Out-Null
                Wait-Health $SourcePort
                $record.SourceHealthRecovered = $true
            } catch { $record.SourceHealthRecovered = $false; $record.Status = 'source-recovery-needs-attention' }
        }
        $record.EndedUtc = [DateTime]::UtcNow.ToString('o')
        Save-PrivateJson (Join-Path $Private 'backup-manifest.json') $record
    }
    if ($record.Status -eq 'source-recovery-needs-attention') { throw 'Original UI recovery needs coordinator attention.' }
    Write-Output 'Archive created in protected private directory. Restore and authenticated checks are pending.'
    return
}

if (-not (Test-Path -LiteralPath $Private -PathType Container)) { throw 'Backup directory absent.' }
$manifest = Get-Content -Raw -LiteralPath (Join-Path $Private 'backup-manifest.json') | ConvertFrom-Json
if ($manifest.Status -ne 'archive-created-restore-pending' -or $manifest.Source -ne $SourceName -or $manifest.SourceVolume -ne $SourceVolume -or $manifest.SourcePort -ne $SourcePort -or $manifest.Image -ne $Image) {
    throw 'Backup manifest is not a complete archive from the reviewed lab.'
}
$archive = Join-Path $Private 'data.tar.gz'
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.Archive.sha256) {
    throw 'Archive hash mismatch. No restore resources have been created.'
}
$RestoreVolume = $RestoreName + '-data'
$names = @(Invoke-LabDocker @('ps','-a','--format','{{.Names}}'))
$volumes = @(Invoke-LabDocker @('volume','ls','--format','{{.Name}}'))
if ($names -contains $RestoreName -or $volumes -contains $RestoreVolume) { throw 'Restore resource exists; use a fresh attempt name.' }
if (@(Get-NetTCPConnection -State Listen -LocalPort $RestorePort -ErrorAction SilentlyContinue).Count) { throw 'Restore port is occupied.' }
$restoreEnv = Join-Path $Private ($RestoreName + '-secret.env')
if (Test-Path -LiteralPath $restoreEnv) { throw 'Restore env file already exists; use a fresh attempt.' }
$sealed = [IO.File]::ReadAllBytes((Join-Path $Private 'secret-env.dpapi'))
$secret = [Security.Cryptography.ProtectedData]::Unprotect($sealed, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
try { [IO.File]::WriteAllBytes($restoreEnv, $secret) }
finally { if ($secret) { [Array]::Clear($secret, 0, $secret.Length) } }
# This plaintext private env copy inherits the restricted ACL. Never include it in evidence.
$result = [ordered]@{ Status='started'; RestoreName=$RestoreName; RestoreVolume=$RestoreVolume;
    RestorePort=$RestorePort; StartedUtc=[DateTime]::UtcNow.ToString('o');
    SourceName=$SourceName; ArchiveSha256=$manifest.Archive.sha256; ApplicationRestoreVerified=$false }
try {
    Invoke-LabDocker @('volume','create','--label','book=local-llm-refresh-l06',$RestoreVolume) | Out-Null
    $result.Extraction = Run-Worker 'restore' $RestoreVolume $Private
    # Read-write mount on this stopped COPY allows SQLite to recover its own WAL bookkeeping if needed.
    # quick_check itself uses a read-only SQLite connection; original volume never mounted here.
    $result.DatabaseCheck = Run-Worker 'check' $RestoreVolume $Private
    $run = @('run','-d','--pull','never','--name',$RestoreName,'--network','bridge','--restart','no',
        '-p',"127.0.0.1:${RestorePort}:8080",'--mount',"type=volume,src=$RestoreVolume,dst=/app/backend/data,volume-nocopy",
        '--env-file',$restoreEnv,'-e','OLLAMA_BASE_URL=http://host.docker.internal:11434',
        '-e','WEBUI_AUTH=True','-e',"WEBUI_URL=http://127.0.0.1:$RestorePort",$Image)
    $result.RestoreId = Invoke-LabDocker $run
    Wait-Health $RestorePort
    $result.SelectedState = Selected-Container $RestoreName
    $result.Status = 'restore-health-ready-authenticated-verification-pending'
} catch {
    $result.Status = 'restore-failed-preserved-for-diagnosis'
    $result.FailureType = $_.Exception.GetType().Name
    # Quarantine only a container with the exact newly-created restore name; never touch source.
    if (@(Invoke-LabDocker @('ps','--format','{{.Names}}')) -contains $RestoreName) {
        Invoke-LabDocker @('stop','--time','30',$RestoreName) | Out-Null
    }
    throw
} finally {
    $result.EndedUtc = [DateTime]::UtcNow.ToString('o')
    Save-PrivateJson (Join-Path $Private ($RestoreName + '-restore.json')) $result
}
Write-Output 'Restore health is ready. Verify the existing account, chats, uploads, citations and provider before claiming a restore pass.'
