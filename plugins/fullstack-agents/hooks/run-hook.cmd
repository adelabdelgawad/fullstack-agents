:; d=$(dirname "$0"); s=$1; shift; exec bash "$d/$s" "$@" # POSIX shells dispatch here and never read the batch below
@echo off
REM Cross-platform hook launcher.
REM
REM POSIX shells (Linux/macOS `sh`/`bash`) execute the first line: it execs the
REM named bash hook and the process is replaced before the batch is ever read.
REM The trailing `#` comment absorbs the CRLF carriage return, so the dispatch
REM works even though this file ships with CRLF line endings.
REM
REM Windows cmd.exe treats that first line as a label, skips it, and runs this
REM batch, which locates bash and runs the hook. Hook scripts use extensionless
REM filenames (e.g. "session-start") so editors and tooling never mistake them
REM for shell scripts the host shell should reinterpret.
REM
REM Usage: run-hook.cmd <script-name> [args...]

if "%~1"=="" (
    echo run-hook.cmd: missing script name >&2
    exit /b 1
)

set "HOOK_DIR=%~dp0"

REM Try Git for Windows bash in standard locations
if exist "C:\Program Files\Git\bin\bash.exe" (
    "C:\Program Files\Git\bin\bash.exe" "%HOOK_DIR%%~1" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)
if exist "C:\Program Files (x86)\Git\bin\bash.exe" (
    "C:\Program Files (x86)\Git\bin\bash.exe" "%HOOK_DIR%%~1" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)

REM Try bash on PATH (e.g. user-installed Git Bash, MSYS2, Cygwin)
where bash >nul 2>nul
if %ERRORLEVEL% equ 0 (
    bash "%HOOK_DIR%%~1" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)

REM No bash found - exit silently rather than error
REM (plugin still works, just without SessionStart context injection)
exit /b 0
