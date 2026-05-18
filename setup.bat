@echo off
title CeraMIS - Diegimas

echo =========================================================
echo             CeraMIS - Diegimo Vedlys
echo =========================================================
echo.

:: 1. Tikriname ar Python yra idiegtas sistemoje
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [KLAIDA] Python nerastas jusu kompiuteryje!
    echo Prasome atsisiusti ir idiegti Python 3.10 arba naujesni is:
    echo https://www.python.org/downloads/
    echo.
    echo SVARBU: Diegiant BUTINAI pazymekite varnele "Add Python to PATH"!
    echo.
    pause
    exit /b
)

:: 2. Kuriame virtualia aplinka (.venv)
if not exist ".venv" (
    echo [VIRTUALI APLINKA] Kuriama nauja virtuali aplinka '.venv'...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [KLAIDA] Nepavyko sukurti virtualios aplinkos.
        pause
        exit /b
    )
    echo [SEKME] Virtuali aplinka sukurta sekmingai.
) else (
    echo [VIRTUALI APLINKA] '.venv' aplinka jau egzistuoja. Tesiama...
)

:: 3. Paleidziame biblioteku diegimo skripta
echo [DIEGIMAS] Vykdomas biblioteku diegimo procesas...
.venv\Scripts\python.exe setup.py
if %errorlevel% neq 0 (
    echo.
    echo [KLAIDA] Diegimo metu ivyko klaida.
    pause
    exit /b
)

:: 4. Kuriame patogu paleidimo faila (run.bat)
echo [PALEIDIMO FAILAS] Kuriama 'run.bat' nuoroda...
(
echo @echo off
echo title CeraMIS
echo echo Paleidziama CeraMIS...
echo start "" ".venv\Scripts\pythonw.exe" "main CeraMIS.py"
) > run.bat

echo [SEKME] 'run.bat' failas sekmingai sukurtas!
echo Dabar galite paleisti programa tiesiog dukart spusteleje 'run.bat'.
echo.
pause
