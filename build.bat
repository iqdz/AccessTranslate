@echo off
REM Double-click wrapper for build.ps1
REM Builds Access-Translate.exe. No admin rights needed for this step.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
