# The Local LLM Home Lab — code companion

Code and synthetic fixtures for the second edition of *The Local LLM Home Lab*. The code release is **v1.0.0**, tagged **book-edition-02-v1.0.0**; code versions and book edition numbers are separate. The second edition is available on Amazon: [Kindle](https://www.amazon.com/dp/B0HPRPRCTL) and [paperback](https://www.amazon.com/dp/B0HPRFZVQW).

Repository: https://github.com/chasesaurabh/local-llm-home-lab

Book-matched release: https://github.com/chasesaurabh/local-llm-home-lab/releases/tag/book-edition-02-v1.0.0

Use the release's `local-llm-home-lab-companion-v1.0.0.zip` asset and check its SHA-256 against `SHA256SUMS.txt`. The ZIP contains a single `local-llm-home-lab` directory; the measurement, recovery and health helpers are in `labs/operations` beneath it. Keep the original archive and use a fresh working copy. This release preserves the reviewed v004 code and fixtures; only publication documentation changed.

Licensed under **MIT**. Copyright (c) 2026 Saurabh Chase; see [LICENSE](LICENSE) and [license scope](LICENSE-NOTICE.md). [release-map.json](release-map.json) records the intended book mapping and verified test boundaries. The tag identifies the exact Git commit; publication observations and asset hashes are recorded with the release, avoiding a self-referential commit field inside its own commit.

These small labs use synthetic inputs. They include no book chapters, covers, teaching figures, model weights, application database, credentials or private run reports. The two PNGs are generated test inputs for vision, not book artwork. Chapter numbers below match the assembled six-part manuscript manifest checked for this candidate; source filenames retain their earlier numbers.

## Choose the lab

| Source chapter | Folder | Purpose | Immediate dependencies |
|---|---|---|---|
| 25 | `labs/llamacpp` | One bounded chat request fixture | Already-running pinned llama.cpp CPU server and downloaded model; see its README |
| 10 | `labs/rag` | Inspect lexical retrieval, stale sources, updates, deletion and injection | Python only; no model, Docker or network |
| 28 | `labs/coding` | Propose a repair to an intentionally broken function | Python; native Ollama and the named coder model only for proposal generation |
| 29 | `labs/vision` | Visible/absent/partial-label checks | Python; native Ollama and the named vision model |
| 30 | `labs/agent` | State-gated read/draft/finish controller | Python; native Ollama and named instruction model only for live loop |
| 24 | `labs/shared` | Read probes for one synthetic collection/file identity | Python; existing authenticated Open WebUI lab and exact collection/file IDs |
| 18–20 | `labs/operations` | Streaming measurement, health snapshots and separate-copy restore | Measurement: Python/Ollama; recovery: Windows PowerShell/Docker Desktop/established WebUI lab |

## Working copy and Python

Retain the original release archive with its accompanying SHA-256 checksum file. Run exercises in a fresh working copy because several examples create output beside their code. The following PowerShell starts from this package's root folder; choose an existing lab root if yours differs:

```powershell
$Package = (Get-Location).Path
$LabRoot = Join-Path $env:USERPROFILE 'local-llm-lab'
if (-not (Test-Path -LiteralPath $LabRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $LabRoot | Out-Null
}
$Work = Join-Path $LabRoot 'companion-work-001'
if (Test-Path -LiteralPath $Work) { throw 'Choose a fresh work folder.' }
Copy-Item -LiteralPath $Package -Destination $Work -Recurse
Set-Location $Work
$Python = (& py -3.12 -c 'import sys; print(sys.executable)').Trim()
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Select an installed Python 3.12 interpreter before continuing.'
}
& $Python --version
```

The recorded interpreter was Python 3.12.14. Python source uses the standard library; there is no pip dependency set. Python installation/bootstrap was not exercised in qualification. If Python is absent, follow the official [Windows Python instructions](https://docs.python.org/3/using/windows.html), then reopen PowerShell and select the installed 3.12 interpreter. Do not point `$Python` at a model or script file. PowerShell execution policy may require your normal approved script-running procedure; these examples do not change it.

The native Ollama labs expect an existing service on `http://127.0.0.1:11434`. They do not install or start it. The recorded runtime was **0.40.12**. Check its identity and cached model inventory before using live examples:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/version
(Invoke-RestMethod http://127.0.0.1:11434/api/tags).models |
    Select-Object name,digest,size
```

| Use | Exact tested model name | Recorded artifact digest |
|---|---|---|
| Measurement, agent | `qwen3:4b-instruct-2507-q4_K_M` | `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0` |
| Coding | `qwen2.5-coder:7b-instruct-q4_K_M` | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |
| Vision | `qwen3-vl:2b` | `0635d9d857d497aeadba3d7d27485746c50554446f9f6ec01ef39788221adbe8` |

Use only the model for your chosen exercise. If it is absent, acquire it through your existing Ollama setup and compare the returned digest before claiming a reproduction. The measurement harness enforces version/digest identity; the smaller coding/vision/agent clients use fixed tags but do not enforce digests. A tag can resolve differently later. The generic `qwen3:4b` tag is not a substitute for the tested instruction model. [Ollama's chat API](https://docs.ollama.com/api/chat) documents the request fields; requested `think: false` does not by itself prove no thinking occurred.

## Retrieval without a model

```powershell
Push-Location (Join-Path $Work 'labs\rag')
& $Python -B -m unittest -v test_harness
& $Python .\retrieval_baseline.py evaluate --top-k 4
& $Python .\retrieval_baseline.py query --scenario baseline `
    --question 'What is the current backup folder?' --top-k 4
& $Python .\retrieval_baseline.py prompts --top-k 4 --output prompts-001.json
Pop-Location
```

The helper reads `cases.json`, `scenarios.json`, `corpus/` and `changes/` relative to itself. Its CLI help retains the original label “rag-prep-relative”; in this package that means the `labs/rag` folder. Output paths must remain beneath that folder, but existing JSON outputs can be overwritten: use fresh names. `evaluate` measures required-chunk coverage, not answer correctness. The 20-case set has 18 scored retrieval cases and two unscored empty-evidence cases. Seven deterministic harness tests exercise boundaries. The UPS note intentionally contains a hostile instruction; treat it as test data, never authority. `score --answers answers-001.json` accepts a separately obtained JSON array with `case_id`, `answer`, `citations`, `abstained`; keyword gates still require manual factual and citation review. No live generation runner or UI credential helper is bundled with this baseline.

## Coding repair

```powershell
Push-Location (Join-Path $Work 'labs\coding')
& $Python -B -m unittest -v
# Expect two failures among five tests: the baseline is deliberately wrong.
& $Python .\propose.py
Pop-Location
```

`propose.py` executes the supplied deterministic tests and sends only the two synthetic Python files and their test output to local Ollama. It writes `baseline-tests.txt`, `request.json`, and `proposal.json`; it never executes the model's answer. It refuses an existing proposal, but can rewrite the baseline log before that check, so start a new working copy for another proposal. Read the returned complete function, compare its boundary policy, manually edit only `retention.py`, and rerun the same five tests. The correct policy keeps age equal to the retention limit; only strictly older items are candidates after restore verification. This function never reads or deletes actual snapshots. Preserve your original source before editing. Earlier failed proposals are not bundled; qualification used a manually reviewed minimal boundary change and passed all five unchanged tests. It was one exercise with prompt/model revisions, not a controlled model ranking.

## Vision fixtures

```powershell
Push-Location (Join-Path $Work 'labs\vision')
& $Python .\vision_lab.py ask --image clear.png --case visible --output visible-001.json
& $Python .\vision_lab.py ask --image clear.png --case absent --output absent-001.json
& $Python .\vision_lab.py ask --image partial.png --case partial --output partial-001.json
Pop-Location
```

Inspect the input PNGs first. The visible case should identify a red square left, blue circle right, and `BOX42`; the absent manufacturer serial number should be reported as not visible; the partial label is only `BOX`. The client refuses an existing result. `vision_lab.py fixtures` regenerates identical inputs only in a folder where neither input exists; the delivered images are already present. Four recorded requests covered these three cases and both images. Thinking text was present despite requested false; no broad OCR, privacy or speed claim follows.

## Bounded agent

```powershell
Push-Location (Join-Path $Work 'labs\agent')
& $Python -B -m unittest -v test_controller
& $Python .\curator.py (Join-Path $LabRoot 'agent-draft-001')
Pop-Location
```

Use a fresh draft path. The controller reads exactly three supplied note IDs, requires all three reads before one bounded `index-draft.md`, then finishes. It has no shell, arbitrary path or outbound-message tool. Review the draft and `trace.json`; a structurally valid source list does not establish factual support.

V004 is the current helper. Its 21 deterministic tests cover permissions, detached request histories, complete workflow, fractional timeouts, late responses, parsing/validation time, draft creation, oversized responses, request failures and the existing step/denial bounds. One monotonic deadline supplies a **cooperative 180-second budget**. HTTP admission uses the positive remaining time capped at 60 seconds; response bodies are read in bounded chunks with a **128 KiB limit** and deadline checks between reads. Checks also occur before tool effects. This is not hard process termination: a blocking operation or an action already in progress can finish after expiry, and backend inference is not cancelled. Diagnostic trace writing remains available after expiry. Six requests, two denials and the existing output/token limits remain bounded; this is not a general agent sandbox.

The final-code delayed-response experiment used a real localhost HTTP server and a shortened in-memory 1.0-second budget. It stopped after approximately **1.016 seconds** during a slow body read, retained the failure trace and created **no draft**; only three synthetic note reads had executed. This was a controlled HTTP experiment, not Ollama inference or proof of exact one-second termination.

The separate current-code Ollama qualification `agent-deadline-live-016/run-001` recorded approximately **3.328 seconds** and five correct actions: three approved reads, one source-linked draft with the checked maintenance/restore facts, and finish. Request histories contained 2, 4, 6, 8 and 10 messages. Independent saved-evidence review passed within that single happy-path scope. No expiry occurred in that run; deadline rejection is established by the separate deterministic and delayed-localhost checks. This is one observed run, not a performance benchmark, reliability rate or general security assurance.

Historical `agent-011/run-04` qualified detached logging and five-action completion for the earlier helper distributed in v001-v003. That run and its eight-test result remain historical evidence for those old bytes; they do not qualify v004's deadline correction.

## Shared collection probes

Create only a synthetic collection and upload `labs/shared/permission-note.md` through your existing Open WebUI lab. For transitions, use separate synthetic owner/member accounts, record the exact collection and file UUIDs from your instance, and retain the same IDs when changing grants. No account, grant, collection or session mutation is performed by this wrapper. From the package working copy:

```powershell
$CollectionId = Read-Host 'Synthetic collection UUID'
$FileId = Read-Host 'Synthetic permission-note.md file UUID'
& $Python .\labs\shared\access_probe.py $CollectionId `
    (Join-Path $LabRoot 'access-owner-001.json') --file-id $FileId --port 3106
```

The command prompts for synthetic login credentials; they are held in memory and not written to the result. Port 3103 selects the original lab; 3106 selects the standard restored copy. The existing UI must be ready on the selected port. Omit `--file-id` only to try owner discovery of the sole exact filename; that discovery branch and interactive prompts were not replayed during qualification. The output's parent must already exist; existing output files are refused.

The unchanged `main` and HTTP routines were exercised as administrator on port 3106 with known collection/file IDs and prompt functions substituted in memory. Metadata/retrieval/file routes returned 200; retrieved and original content contained the sentinel; original-content hash matched the fixture. Metadata need not include document text. Separate underlying access tests exercised owner/member grant/revoke/session boundaries, but **the complete reader wrapper was not replayed across those transitions**. A fresh login per invocation cannot prove revocation of an already-issued token. Do not use this tool on a private collection: successful retrieval text is recorded in the output.

## Measurement, health and restore

See [operations/README.md](labs/operations/README.md) for the full plan/execute commands, source and target guards, exact prerequisites and qualification scope. `$Python` is selected above, so that README's Chapter 18 reference does not require an unpublished helper. Measurement and backup/restore scripts remain byte-for-byte the previously qualified reader sources. Health v002 adds optional NVIDIA discovery and its separate qualification below; this README and the operations README use the assembled chapter numbering.

From `labs/operations`, `measure_lab.py --plan` and `Backup-Restore-Lab.ps1 -Mode Plan` make no service calls. Real measurement unloads only its selected model and performs 18 bounded streaming requests; coordinate a quiet request window. Cold-after-unload does not mean OS caches were flushed. First-content timing is the first nonempty answer NDJSON event seen by the client. Shared-host samples are not dedicated model resource measurements or peaks; concurrency does not prove parallel inference. Inspect every answer yourself.

Recovery requires an **existing** Windows lab: Docker Desktop Linux context `desktop-linux`, cached pinned Open WebUI 0.12.4 image, owned source `local-llm-l03-001`, named volume `local-llm-l03-001-data`, loopback port 3103 and the existing protected `$LabRoot\webui\webui.env`. The image digest is in the script. The helper stops/restarts that owned application for a quiesced full-volume archive, then restores to a fresh separate volume/container/port. It neither installs Docker nor constructs the original lab. Existing-secret recovery matters; do not substitute a new secret. [Open WebUI's setup documentation](https://docs.openwebui.com/getting-started/quick-start/) describes the application's persistent data and secret concepts; its evolving default commands are not this pinned lab.

The archive has restricted NTFS access but is not independently encrypted. Its sealed secret uses same-user Windows DPAPI; off-device/lost-host recovery is unproven. Authenticate to the restored copy and verify chats, exact document contents, memberships, a real cited response, and the original lab. Health/SQLite checks alone do not establish recovery. Reader backup/restore was executed in PowerShell 5.1 on a separate test port 3108. Standard source/restore health and stopped-copy checks were executed in PowerShell 5.1 and 7.6.5 on ports 3103/3106.

`Get-LabHealth.ps1` requires Windows CIM/network commands and Docker CLI. NVIDIA telemetry is optional: an absent executable records `GpuQueryStatus=unavailable`, reason `executable-not-found`, and null GPU exit/data fields; a failed query records `error`. These states are not zero usage and do not identify the physical GPU backend. It accepts only matching 3103/source or 3106/restore pairs, not the 3108 qualification copy. Its `-OutputPath` must be a fresh path below the script folder; the error message identifies that actual script folder. Omitting `-OutputPath` prints JSON. For example:

```powershell
Push-Location (Join-Path $Work 'labs\operations')
.\Get-LabHealth.ps1 -UiPort 3106 -ContainerName local-llm-l06-001 `
    -OutputPath (Join-Path $PWD 'health-restored-001.json')
Pop-Location
```

## Validation and limits

The candidate's local manifest records exact bytes; preserve it and never silently replace it. The original live qualifications are described per helper above. V002 additionally completed eight read-only health snapshots: source3103 and restore3106 in both PowerShell versions, with the actual NVIDIA tool available and with only child-process PATH excluding it while retaining Docker. All non-GPU checks still completed; every child PATH was restored. This was the same NVIDIA host, not a physical CPU-only host. No inference, backup, account action or service change was repeated for v002. Offline staging checks cover source syntax, known synthetic fixture identities, deterministic tests, and explicit file exclusions. No Apple Silicon, bare-metal Linux, AMD GPU, internet-isolated household deployment or universal package compatibility is established. See [SECURITY.md](SECURITY.md) for handling private output and [CONTRIBUTING.md](CONTRIBUTING.md) for proposed contribution rules. V003 added the approved MIT license and selected repository destination. V004 supersedes v003 with the agent deadline/response-bound correction, its expanded 21-test suite and the qualification described above. The other 35 package files are unchanged from v003; only the two agent Python files, this README and release-map.json changed. The saved qualifications were reviewed during v004 packaging; no live test was rerun for packaging. A release still needs a verified public destination, immutable commit/tag, final distribution checks and book/repository linkage. The local pre-push review does not establish that installed runtimes or models are vulnerability-free.
