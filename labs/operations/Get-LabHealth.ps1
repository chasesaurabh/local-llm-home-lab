# Read-only L07 snapshot: no inference, model loading, service control, credentials or databases.
[CmdletBinding()]
param(
    [string]$OutputPath,
    [ValidateSet(3103,3106)][int]$UiPort = 3103,
    [ValidateSet('local-llm-l03-001','local-llm-l06-001')][string]$ContainerName = 'local-llm-l03-001'
)
$ErrorActionPreference = 'Stop'
$ExpectedPort = @{ 'local-llm-l03-001'=3103; 'local-llm-l06-001'=3106 }
if ($UiPort -ne $ExpectedPort[$ContainerName]) {
    throw 'UI/container mismatch: source local-llm-l03-001 requires 3103; restored local-llm-l06-001 requires 3106.'
}
$UiOrigin = "http://127.0.0.1:$UiPort"
$record = [ordered]@{ TimeUtc=[DateTime]::UtcNow.ToString('o'); InferenceAttempted=$false;
    UiPort=$UiPort; ContainerName=$ContainerName; UiOrigin=$UiOrigin }
function Http-Check([string]$Uri, [switch]$Json) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        $reply = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 5
        $value = [ordered]@{ Status=[int]$reply.StatusCode; ElapsedMs=$watch.Elapsed.TotalMilliseconds }
        if ($Json) { $value.Body = $reply.Content | ConvertFrom-Json }
        return $value
    } catch {
        $status = $null
        if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
        return [ordered]@{ Status=$status; ElapsedMs=$watch.Elapsed.TotalMilliseconds; ErrorType=$_.Exception.GetType().Name }
    } finally { $watch.Stop() }
}
$record.OllamaVersion = Http-Check 'http://127.0.0.1:11434/api/version' -Json
$tags = Http-Check 'http://127.0.0.1:11434/api/tags' -Json
$record.InstalledModelsStatus = $tags.Status
if ($tags.Status -eq 200) {
    $record.InstalledModels = @($tags.Body.models | Select-Object name,digest,size)
}
$ps = Http-Check 'http://127.0.0.1:11434/api/ps' -Json
$record.RuntimeModelsStatus = $ps.Status
if ($ps.Status -eq 200) {
    $record.RuntimeModels = @($ps.Body.models | Select-Object name,digest,size,size_vram,context_length,runner)
}
$record.UiHealth = Http-Check "$UiOrigin/health"
# A denial is useful boundary evidence, not an authenticated user-path test.
$record.AnonymousChats = Http-Check "$UiOrigin/api/v1/chats/"
$record.AnonymousModels = Http-Check "$UiOrigin/api/models"
$record.Listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in @(11434,$UiPort) } | Select-Object LocalAddress,LocalPort,OwningProcess)
$os = Get-CimInstance Win32_OperatingSystem
$record.HostRam = [ordered]@{ TotalBytes=[long]$os.TotalVisibleMemorySize*1024; AvailableBytes=[long]$os.FreePhysicalMemory*1024 }
$cpu = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'"
$record.HostCpuBusyPercent = $cpu.PercentProcessorTime
$record.GpuQueryStatus = 'unavailable'
$record.GpuQueryExitCode = $null
$record.GpuCsv = $null
$record.GpuQueryErrorType = $null
$record.GpuQueryReason = 'executable-not-found'
$gpuCommand = Get-Command nvidia-smi -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($gpuCommand) {
    try {
        $gpu = & $gpuCommand.Source --query-gpu=index,name,driver_version,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw --format=csv,noheader,nounits 2>$null
        $record.GpuQueryExitCode = $LASTEXITCODE
        if ($LASTEXITCODE -eq 0 -and @($gpu).Count -gt 0) {
            $record.GpuQueryStatus = 'available'
            $record.GpuQueryReason = $null
            $record.GpuCsv = @($gpu)
        } else {
            $record.GpuQueryStatus = 'error'
            $record.GpuQueryReason = 'query-failed-or-empty'
        }
    } catch {
        $record.GpuQueryStatus = 'error'
        $record.GpuQueryReason = 'query-exception'
        $record.GpuQueryErrorType = $_.Exception.GetType().Name
    }
}
$record.GpuCsvColumns = @('index','name','driver_version','total_MiB','used_MiB','free_MiB','gpu_percent','temperature_C','power_W')
$format = '{"id":{{json .Id}},"image":{{json .Image}},"state":{{json .State.Status}},"ports":{{json .HostConfig.PortBindings}},"restart_policy":{{json .HostConfig.RestartPolicy.Name}}}'
$selected = & docker inspect --format $format $ContainerName
$record.ContainerQueryExitCode = $LASTEXITCODE
if ($LASTEXITCODE -eq 0) { $record.UiContainer = ($selected -join "`n") | ConvertFrom-Json }
$stats = & docker stats --no-stream --format '{{json .}}' $ContainerName
$record.ContainerStatsExitCode = $LASTEXITCODE
if ($LASTEXITCODE -eq 0) { $record.UiContainerStats = ($stats -join "`n") | ConvertFrom-Json }
$record.Limits = @('No authenticated UI, generation, retrieval or restore assertion.',
    'Shared-host values are a snapshot; sampled GPU usage is not model allocation or peak.',
    'Unavailable or failed NVIDIA telemetry is not zero usage and does not establish CPU-only hardware.',
    'Container resource counters describe the Docker Linux VM accounting, not exclusive Windows host usage.',
    'Listener bindings do not replace a denied-path test from another device.')
$json = $record | ConvertTo-Json -Depth 20
if ($OutputPath) {
    $full = [IO.Path]::GetFullPath($OutputPath)
    $allowed = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
    if (-not $full.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) { throw "Output must stay under the script folder: $PSScriptRoot" }
    if (Test-Path -LiteralPath $full) { throw 'Refusing to overwrite a health snapshot.' }
    $json | Set-Content -LiteralPath $full -Encoding UTF8
} else { $json }
