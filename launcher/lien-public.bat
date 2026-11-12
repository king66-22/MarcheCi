@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
title MarcheCI - lien public temporaire

echo ============================================================
echo  MarcheCI : publication temporaire du site sur Internet
echo ============================================================
echo.
echo Ce script ouvre un tunnel Cloudflare vers le site local.
echo Le site reste sur CET ordinateur : il doit rester allume et
echo la pile Docker doit tourner (launcher\demarrer.bat).
echo.

rem --- Le site local doit repondre avant d'ouvrir le tunnel.
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -Uri 'http://localhost:80/health' -UseBasicParsing -TimeoutSec 5; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo [ERREUR] Le site local ne repond pas sur http://localhost.
  echo          Demarrez d'abord la pile avec launcher\demarrer.bat
  echo.
  pause
  exit /b 1
)

rem --- cloudflared : deja installe, sinon tools\, sinon telechargement.
set "CLOUDFLARED="
where cloudflared >nul 2>&1 && set "CLOUDFLARED=cloudflared"
if not defined CLOUDFLARED if exist "%ProgramFiles(x86)%\cloudflared\cloudflared.exe" set "CLOUDFLARED=%ProgramFiles(x86)%\cloudflared\cloudflared.exe"
if not defined CLOUDFLARED if exist "%ProgramFiles%\cloudflared\cloudflared.exe" set "CLOUDFLARED=%ProgramFiles%\cloudflared\cloudflared.exe"
if not defined CLOUDFLARED if exist "%~dp0..\tools\cloudflared.exe" set "CLOUDFLARED=%~dp0..\tools\cloudflared.exe"
if not defined CLOUDFLARED (
  echo Telechargement de cloudflared ^(~40 Mo, une seule fois^)...
  powershell -NoProfile -Command "New-Item -ItemType Directory -Force tools | Out-Null; Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'tools\cloudflared.exe'"
  if errorlevel 1 (
    echo [ERREUR] Telechargement impossible. Verifiez la connexion Internet.
    pause
    exit /b 1
  )
  set "CLOUDFLARED=tools\cloudflared.exe"
)

echo Ouverture du tunnel. L'adresse publique apparait ci-dessous,
echo a la ligne https://................trycloudflare.com
echo Laissez cette fenetre ouverte pendant toute la demonstration.
echo.
"%CLOUDFLARED%" tunnel --url http://localhost:80 --no-autoupdate

echo.
echo Tunnel ferme : le site n'est plus accessible depuis Internet.
pause
