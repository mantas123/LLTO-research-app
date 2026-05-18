@echo off
chcp 65001 > nul
title CeraMIS
echo Paleidziama CeraMIS...
start "" ".venv\Scripts\pythonw.exe" "main CeraMIS.py"
