@echo off
rem ===========================================================================
rem  strcodec launcher for Windows
rem  Runs the strcodec CLI with the CPython 3.10+ that is already on this machine
rem  (the same one spss-clemb-mcp uses). As a fallback, IBM SPSS Modeler 18.5+
rem  ships a CPython under <Modeler>\python that is used when nothing else is found.
rem
rem    .bob\strcodec\strcodec.cmd <strcodec arguments>   e.g.  decode x.str  |  status  |  hook prompt
rem    .bob\strcodec\strcodec.cmd --which                print the interpreter that would be used
rem
rem  Resolution order (first candidate that exists AND passes the check wins):
rem    1. STRCODEC_PYTHON            environment variable: full path to python.exe
rem    2. .bob\strcodec\python.path  text file: first non-empty, non-# line = path to python.exe
rem    3. py -3 (Python launcher)     4. python on PATH
rem    -- fallbacks (Modeler's bundled CPython; not an IBM-supported use) --
rem    5. SPSS_MODELER_CLEMB_PATH    (spss-clemb-mcp's variable) -> <Modeler>\python\python.exe
rem    6. <ProgramW6432 | ProgramFiles | ProgramFiles(x86)>\IBM\SPSS\{Modeler,ModelerServer}\<version>\python\python.exe
rem       newest version directory first -- no product version is hard-coded
rem  Check: CPython, version >= 3.10, starts with "-I -S -B -X utf8" (isolated, no site,
rem  no .pyc written, UTF-8 mode). Nothing is installed or modified anywhere.
rem  The same order is mirrored in pyfind.py (diagnostics: strcodec.cmd python-info).
rem ===========================================================================
setlocal EnableExtensions DisableDelayedExpansion
set "HERE=%~dp0"
set "PYFLAGS=-I -S -B -X utf8"
set "PY="
set "SRC="
set "TRIED="

if defined STRCODEC_PYTHON call :try "%STRCODEC_PYTHON%" STRCODEC_PYTHON
if not defined PY if exist "%HERE%python.path" call :tryfile "%HERE%python.path"
if not defined PY call :trylauncher
if not defined PY call :trypath
if not defined PY if defined SPSS_MODELER_CLEMB_PATH call :tryclemb "%SPSS_MODELER_CLEMB_PATH%"
if not defined PY call :scan "%ProgramW6432%"
if not defined PY call :scan "%ProgramFiles%"
if not defined PY call :scan "%ProgramFiles(x86)%"
if not defined PY goto :fail

if /I "%~1"=="--which" (
  echo %PY%
  echo source=%SRC%
  "%PY%" %PYFLAGS% -c "import platform; print(platform.python_implementation(), platform.python_version())"
  exit /b 0
)
set "STRCODEC_PYTHON_SELECTED=%PY%"
set "STRCODEC_PYTHON_SOURCE=%SRC%"
"%PY%" %PYFLAGS% "%HERE%strcodec.py" %*
exit /b %ERRORLEVEL%

:try
rem %1 = candidate python.exe, %2 = source label
set "CAND=%~1"
if not exist "%CAND%" (
  set "TRIED=%TRIED% [%~2] %CAND% (not found);"
  exit /b 1
)
"%CAND%" %PYFLAGS% -c "import sys; sys.exit(0 if sys.implementation.name == 'cpython' and sys.version_info >= (3, 10) else 3)" >nul 2>&1
if errorlevel 1 (
  set "TRIED=%TRIED% [%~2] %CAND% (not CPython 3.10+ or failed to start);"
  exit /b 1
)
set "PY=%CAND%"
set "SRC=%~2"
exit /b 0

:tryfile
for /f "usebackq eol=# delims=" %%L in ("%~1") do (
  if not defined PY call :try "%%~L" python.path
)
exit /b 0

:tryclemb
rem <Modeler>\bin\clemb.exe  ->  <Modeler>\python\python.exe
set "MHOME="
for %%F in ("%~1") do set "MHOME=%%~dpF"
if defined MHOME call :try "%MHOME%..\python\python.exe" SPSS_MODELER_CLEMB_PATH
exit /b 0

:scan
if "%~1"=="" exit /b 0
for %%P in (Modeler ModelerServer) do (
  if not defined PY if exist "%~1\IBM\SPSS\%%P\" call :scandir "%~1\IBM\SPSS\%%P" %%P
)
exit /b 0

:scandir
for /f "delims=" %%V in ('dir /b /ad /o-n "%~1" 2^>nul') do (
  if not defined PY call :try "%~1\%%V\python\python.exe" modeler_%~2_%%V
)
exit /b 0

:trylauncher
where py >nul 2>&1 || exit /b 0
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
  if not defined PY call :try "%%P" py_launcher
)
exit /b 0

:trypath
for /f "delims=" %%P in ('where python 2^>nul') do (
  if not defined PY call :try "%%P" PATH
)
exit /b 0

:fail
>&2 echo [strcodec] No usable CPython 3.10+ was found. Tried:%TRIED%
>&2 echo [strcodec] Fix: install CPython 3.10+ (the one spss-clemb-mcp uses is fine) so that `py -3` or `python` finds it,
>&2 echo [strcodec]      or set STRCODEC_PYTHON=^<path\to\python.exe^>   or write that path into %HERE%python.path
>&2 echo [strcodec] Fallback: IBM SPSS Modeler 18.5+ ships CPython at ^<Modeler install dir^>\python\python.exe
exit /b 9
