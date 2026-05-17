@echo off
title LLTO Comprehensive App - Siuntimas i GitHub

echo =========================================================
echo       LLTO Comprehensive App - GitHub irankis
echo =========================================================
echo.

:: Patikriname ar Git yra idiegtas
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [KLAIDA] Kompiuteryje nerastas idiegtas 'git'!
    echo Prasome atsisiusti ir idiegti Git is: https://git-scm.com/
    echo Po idiegimo paleiskite si faila is naujo.
    echo.
    pause
    exit /b
)

echo Pasirinkite, kaip norite paruosti repozitoriju:
echo [1] Svarus startas (Rekomenduojama)
echo     - Sukurs visiskai nauja repozitoriju tik su jusu LLTO failais.
echo     - Pasalins sena PyEIS istorija, todel projektas bus lengvas.
echo [2] Islaikyti senaja istorija
echo     - Issaugos visa istorine PyEIS kurimo eiga.
echo.

set /p pasirinkimas="Iveskite pasirinkima [1 arba 2]: "

if "%pasirinkimas%"=="1" (
    echo.
    echo [PROCESAS] Valomas senasis .git aplankas...
    if exist ".git" (
        rmdir /s /q .git
    )
    echo [PROCESAS] Inicializuojama nauja Git repozitorija...
    git init
    git branch -M main
    echo [SEKME] Svari repozitorija sekmingai inicializuota.
) else (
    echo.
    echo [PROCESAS] Tesiama su esama istorija...
    git branch -M main >nul 2>&1
)

echo.
echo [PROCESAS] Nustatomas GitHub adresas: https://github.com/mantas123/LLTO-research-app.git
set git_url=https://github.com/mantas123/LLTO-research-app.git

:: Nustatome nauja remote origin
git remote remove origin >nul 2>&1
git remote add origin %git_url%
if %errorlevel% neq 0 (
    echo [KLAIDA] Nepavyko prideti remote adreso: %git_url%
    pause
    exit /b
)

echo.
echo [PROCESAS] Ruosiami failai ikelimui (pagal .gitignore taisykles)...
git add .

echo.
echo [PROCESAS] Nustatoma vietine Git tapatybe...
git config user.email "mantas123@users.noreply.github.com"
git config user.name "mantas123"

echo.
echo [PROCESAS] Kuriamas pirmasis commit pranesimas...
git commit -m "Initial commit: LLTO Comprehensive App"

echo.
echo [PROCESAS] Failai siunciami i jusu GitHub repozitoriju...
echo (Gali issokti GitHub prisijungimo langas vartotojo patvirtinimui)
echo.
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [ISPEJIMAS] Nepavyko issiusti i pagrindine 'main' saka.
    echo Bandoma siusti i 'master' saka...
    git push -u origin master
)

echo.
echo =========================================================
echo         DARBAS BAIGTAS: Projekto failai GitHub!
echo =========================================================
echo.
pause
