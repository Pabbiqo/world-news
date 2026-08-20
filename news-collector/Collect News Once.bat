@echo off
setlocal
cd /d "%~dp0\..\.."
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 tools\news-collector\collect_news.py
) else (
  python tools\news-collector\collect_news.py
)
pause
