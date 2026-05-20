@echo off
title CeraMIS - GitHub Atnaujinimas

echo =========================================================
echo             CeraMIS - GitHub Atnaujinimas
echo =========================================================
echo.

:: 1. Patikriname ar Git yra idiegtas
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [KLAIDA] Git nerastas jūsų sistemoje!
    pause
    exit /b
)

:: 2. Parodome esamus pakeitimus
echo [PROCESAS] Tikrinami atlikti kodo pakeitimai...
echo ---------------------------------------------------------
git status -s
echo ---------------------------------------------------------
echo.

:: Patikriname ar yra kokiu nors pakeitimu
git status --porcelain | findstr /R "^" >nul
if %errorlevel% neq 0 (
    echo [PASTABA] Pakeitimu nerasta. Jusu kodas jau sutampa su GitHub!
    echo.
    pause
    exit /b
)

:: 3. Prasome vartotojo ivesti pakeitimo aprasyma
set /p msg="Iveskite pakeitimo aprasyma (pvz. 'atnaujintos spalvos') [spauskite Enter standartiniam]: "

if "%msg%"=="" (
    :: Jeigu nieko neivede, sugeneruojame automatini aprasyma su data
    for /f "tokens=2 delims==" %%i in ('wmic os get localdatetime /value') do set datetime=%%i
    set date_str=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2% %datetime:~8,2%:%datetime:~10,2%
    set msg=CeraMIS atnaujinimas - %date_str%
)

echo.
echo [PROCESAS] Siunciami pakeitimai i GitHub...
echo.

:: 4. Vykdome Git komandas
echo --- Pridedami nauji failai...
git add .

echo --- Issaugomi pakeitimai (commit)...
git commit -m "%msg%"

echo --- Siunciama i GitHub (push)...
git push origin main
if %errorlevel% neq 0 (
    git push origin master
)

echo.
echo =========================================================
echo      SEKME: Pakeitimai sekmingai patalpinti GitHub!
echo =========================================================
echo Pakeitimo aprasymas: %msg%
echo.
pause
