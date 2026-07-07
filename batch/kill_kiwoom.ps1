# Kill all processes attached to the current console (Phase cleanup)
# GetConsoleProcessList() returns every PID attached to THIS console window —
# no path/name guessing needed; catches any process that would keep the window open.
$ErrorActionPreference = 'SilentlyContinue'

try {
    Add-Type -Name ConsoleHelper -Namespace Win32 -MemberDefinition '
[DllImport("kernel32.dll")]
public static extern uint GetConsoleProcessList(uint[] lpdwProcessList, uint dwProcessCount);
'
} catch {}

$list = New-Object uint[] 128
$cnt = [Win32.ConsoleHelper]::GetConsoleProcessList($list, 128)

$myPid    = $PID
$parentPid = [int](Get-WmiObject Win32_Process -Filter "ProcessId=$PID").ParentProcessId

$killed = 0
for ($i = 0; $i -lt $cnt; $i++) {
    $p = [int]$list[$i]
    if ($p -ne 0 -and $p -ne $myPid -and $p -ne $parentPid) {
        $name = try { (Get-Process -Id $p).ProcessName } catch { "?" }
        Write-Output "  [kill_kiwoom] PID=$p Name=$name"
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        $killed++
    }
}

Write-Output "[kill_kiwoom] $killed process(es) killed from console group"
