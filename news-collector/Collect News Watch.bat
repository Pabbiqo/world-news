@echo off
setlocal
cd /d "%~dp0\..\.."
echo Updating World news every 300 seconds. Close this window to stop.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 tools\news-collector\collect_news.py --watch 300
) else (
  python tools\news-collector\collect_news.py --watch 300
)
pause
