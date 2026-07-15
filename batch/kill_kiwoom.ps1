# Kill Kiwoom and all child + orphaned CEF/Chrome processes
# Kiwoom spawns chromedriver.exe which inherits the LOG file handle.
# chromedriver.exe is never used by regular Chrome browser -- safe to kill unconditionally.
$ErrorActionPreference = 'SilentlyContinue'

function Kill-ProcessTree {
    param([int]$Pid)
    Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $Pid } | ForEach-Object {
        Kill-ProcessTree ([int]$_.ProcessId)
    }
    $name = try { (Get-Process -Id $Pid -ErrorAction SilentlyContinue).ProcessName } catch { '?' }
    Write-Output "  [kill_kiwoom] TREE  PID=$Pid Name=$name"
    Stop-Process -Id $Pid -Force -ErrorAction SilentlyContinue
}

# Step 1: Kill C:\OpenAPI\* process trees
$killed_tree = 0
$roots = @(Get-Process | Where-Object { try { $_.Path -like 'C:\OpenAPI\*' } catch { $false } })
foreach ($proc in $roots) {
    Kill-ProcessTree $proc.Id
    $killed_tree++
}

# Step 2: Kill Kiwoom CEF processes
# - chromedriver.exe: Kiwoom internal driver (never spawned by regular Chrome)
# - chrome/chromium with --remote-debugging-port: Kiwoom CEF browser instance
$killed_cef = 0
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    ($_.Name -like 'chromedriver*') -or
    (($_.Name -like 'chrome*' -or $_.Name -like 'chromium*') -and ($_.CommandLine -like '*--remote-debugging-port*'))
} | ForEach-Object {
    Write-Output "  [kill_kiwoom] CEF   PID=$($_.ProcessId) Name=$($_.Name)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    $killed_cef++
}

# Step 3: Poll until all Kiwoom + CEF processes are gone (max 60s)
$poll = 0
do {
    Start-Sleep -Seconds 3
    $poll++
    $remaining_api = @(Get-Process | Where-Object { try { $_.Path -like 'C:\OpenAPI\*' } catch { $false } })
    $remaining_cef = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        ($_.Name -like 'chromedriver*') -or
        (($_.Name -like 'chrome*' -or $_.Name -like 'chromium*') -and ($_.CommandLine -like '*--remote-debugging-port*'))
    })
    if ($remaining_api.Count -eq 0 -and $remaining_cef.Count -eq 0) { break }
    if ($remaining_api.Count -gt 0) {
        Write-Output "  [kill_kiwoom] waiting... $($remaining_api.Count) OpenAPI proc(s) (poll $poll/20)"
        $remaining_api | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    }
    if ($remaining_cef.Count -gt 0) {
        Write-Output "  [kill_kiwoom] waiting... $($remaining_cef.Count) CEF proc(s) (poll $poll/20)"
        $remaining_cef | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
} while ($poll -lt 20)

Write-Output "[kill_kiwoom] done  tree_roots=$killed_tree  cef=$killed_cef"
