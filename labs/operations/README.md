# Windows recovery and health lab

This folder contains the reader scripts for Chapters 18–20. Keep it outside the private backup directory. They work with the same named Windows lab used earlier in the book. No personal details or secret values are included.

- `Backup-Restore-Lab.ps1` contains its Python archive worker inside the script; Python runs inside the already-cached pinned Open WebUI image. No separate Windows Python installation or author-only helper is required.
- `Get-LabHealth.ps1` makes only health, identity and resource queries. It accepts the source pair `local-llm-l03-001`/3103 or the restored pair `local-llm-l06-001`/3106. It rejects crossed pairs before queries.
- `measure_lab.py` performs the bounded direct-API measurement only with both execution switches. It requires a working Python interpreter and explicit `--lab-root`. It uses the standard library without additional packages. Its timing, inference and sampling functions match the original measured harness.

## Measurement

Follow Chapter 18 to select the Python executable into `$Python`. From this folder, use your existing lab root and a new result directory whose parent already exists:

```powershell
$LabRoot = Join-Path $env:USERPROFILE 'local-llm-lab'
$ResultsRoot = Join-Path $LabRoot 'measurements'
if (-not (Test-Path -LiteralPath $ResultsRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $ResultsRoot | Out-Null
}
$Run = Join-Path $ResultsRoot 'measurement-001'
& $Python .\measure_lab.py --plan --lab-root $LabRoot --output $Run
# After coordinating a quiet lab-request window:
& $Python .\measure_lab.py --lab-root $LabRoot --output $Run `
    --model qwen3:4b-instruct-2507-q4_K_M --execute --exclusive-lab-window
```

An existing result directory, an output outside the selected lab root, or a missing output parent is rejected. Runtime/model identity guards and fixed settings are retained. The default run is 18 requests. Review every quality answer; a completed harness or substring match alone is not an acceptance grade. Each qualification or later performance run gets a fresh directory. Do not combine later qualification timings with the original Chapter 18 worked example.

## Recovery

The recovery script defaults to the existing Chapter 5/9 lab folder, `$env:USERPROFILE\local-llm-lab`, with the existing secret at `webui\webui.env`. Use `-LabRoot` explicitly if your folder differs. Do not generate a different secret for an existing application.

From this folder, inspect the plan:

```powershell
$LabRoot = Join-Path $env:USERPROFILE 'local-llm-lab'
$Private = Join-Path $LabRoot 'recovery\l06-backup-001'
.\Backup-Restore-Lab.ps1 -Mode Plan -LabRoot $LabRoot `
    -PrivateDirectory $Private
```

Coordinate a quiet application window, confirm the source identity and available disk capacity, then perform backup and restore separately:

```powershell
.\Backup-Restore-Lab.ps1 -Mode Backup -LabRoot $LabRoot `
    -PrivateDirectory $Private -Execute -ExclusiveLabWindow
.\Backup-Restore-Lab.ps1 -Mode Restore -LabRoot $LabRoot `
    -PrivateDirectory $Private -RestoreName local-llm-l06-001 `
    -RestorePort 3106 -Execute -ExclusiveLabWindow
```

The source name, volume and port may be supplied explicitly with `-SourceName`, `-SourceVolume` and `-SourcePort`. Defaults are `local-llm-l03-001`, `local-llm-l03-001-data` and 3103. The selected source must match the pinned image, exact data mount and expected single loopback publication. Restore names must use the `local-llm-l06-` prefix. Existing targets, source/target collisions, paths outside the selected lab, reparse paths and archive hash mismatches are rejected. Choose a fresh `l06-backup-*` private directory and fresh restore suffix for another attempt.

The private directory contains the full data archive and a DPAPI-sealed copy of the existing environment file. The restore procedure also creates a private plaintext environment file for the new container, inheriting the restricted directory permissions. Do not publish these files. The archive is restricted by NTFS permissions but **not independently encrypted**. DPAPI CurrentUser depends on the same recoverable Windows profile; this is not verified encrypted off-device or lost-host recovery.

After restore, use the existing account at `http://127.0.0.1:3106`. Verify saved chats, document bytes and memberships, actual retrieval and an opened citation, anonymous denials, and the original instance's usability. A healthy endpoint or SQLite integrity check alone is not a complete pass. Follow Chapters 19–20 for the stopped-copy exercise and failure recovery. No cleanup/prune is automatic; retain the original volume and known-good archive.

Qualification: the portable measurement helper completed all 18 requests with Python 3.12.14/Ollama 0.40.12 and passed manual review of all answers (three distinct synthetic cases). The self-contained reader recovery script completed backup/restore in Windows PowerShell 5.1 using an explicit lab folder and separate test copy on port 3108; two baseline chats, 13 upload contents and three memberships matched, and the bounded cited answer was correct. Original source/restored health and stopped-copy checks ran in both PowerShell 5.1 and 7 on the standard 3103/3106 pairs. These later qualification runs remain separate from the book's original timing and archive examples. Plan mode alone does not establish any of those outcomes.

## Health helper v002 qualification

NVIDIA command discovery is optional. Missing tooling records unavailable telemetry with null values; failed queries record an error rather than fabricated zero usage. Eight read-only snapshots passed on source3103/restored3106 under PowerShell5.1 and7.6.5, with normal discovery and a child-process PATH that hid nvidia-smi while retaining Docker. All child PATH values were restored. This tests missing-tool handling on the same NVIDIA host, not physical CPU-only hardware. No service change or inference was performed.

The unchanged measurement helper's module description still names historical Chapter26; the assembled chapter is18. The unchanged recovery helper's historical Chapter14/15 folder messages refer to assembled Chapters5/9. The executable path/resource guards are unchanged.
