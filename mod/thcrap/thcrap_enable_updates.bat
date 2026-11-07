@echo off
if not exist "%~dp0"\bin\thcrap_update.dll (
move "%~dp0"\bin\thcrap_update_disabled.dll "%~dp0"\bin\thcrap_update.dll
echo Updates enabled
) else (
echo Updates are already enabled
)
pause
(goto) 2>nul & del "%~f0"
