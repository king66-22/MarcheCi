param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('start', 'stop', 'status', 'logs', 'monitoring')]
    [string]$Action,
    [Parameter(Position = 1)]
    [string]$Service = ''
)

$ErrorActionPreference = 'Continue'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
$ComposeFile = 'compose.yaml'
$MonitoringFile = 'monitoring/zabbix/compose.yaml'
$SecretFiles = @(
    'postgres_owner_password.secret', 'catalogue_db_password.secret', 'commandes_db_password.secret',
    'utilisateurs_db_password.secret', 'notifications_db_password.secret', 'catalogue_database_url.secret',
    'commandes_database_url.secret', 'utilisateurs_database_url.secret', 'notifications_database_url.secret',
    'jwt_secret.secret', 'rabbitmq_password.secret', 'svc_commandes_password.secret', 'admin_password.secret',
    'zabbix_db_password.secret'
)
$HealthPaths = @(
    @{ Name = 'Catalogue'; Path = '/api/catalogue/health' },
    @{ Name = 'Commandes'; Path = '/api/commandes/health' },
    @{ Name = 'Utilisateurs'; Path = '/api/utilisateurs/health' },
    @{ Name = 'Notifications'; Path = '/api/notifications/health' }
)

function Fail([string]$Message) {
    Write-Host "[ERREUR] $Message" -ForegroundColor Red
    exit 1
}

function Get-PythonCommand {
    $localPython = Join-Path $Root '.venv\Scripts\python.exe'
    if (Test-Path $localPython) { return @{ Exe = $localPython; Prefix = @() } }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return @{ Exe = $python.Source; Prefix = @() } }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return @{ Exe = $py.Source; Prefix = @('-3') } }
    return $null
}

function Invoke-ConfigCheck {
    $python = Get-PythonCommand
    if (-not $python) { Fail 'Python 3.12+ est requis pour vérifier la configuration et préparer les fichiers secrets. Installez-le puis relancez ce fichier.' }
    & $python.Exe @($python.Prefix) 'scripts/sync_secrets.py' '--check'
    if ($LASTEXITCODE -ne 0) { Fail 'Configuration .env incomplète. Corrigez les valeurs signalées dans .env, puis relancez le démarrage.' }
    $missing = @($SecretFiles | Where-Object { -not (Test-Path (Join-Path $Root "secrets\$_")) })
    if ($missing.Count -gt 0) {
        Write-Host '[INFO] Préparation des fichiers secrets manquants; les fichiers existants seront préservés.' -ForegroundColor Cyan
        & $python.Exe @($python.Prefix) 'scripts/sync_secrets.py' '--missing-only'
        if ($LASTEXITCODE -ne 0) { Fail 'Impossible de préparer les secrets depuis .env.' }
    }
    $stillMissing = @($SecretFiles | Where-Object { -not (Test-Path (Join-Path $Root "secrets\$_")) })
    if ($stillMissing.Count -gt 0) { Fail 'Des fichiers secrets sont toujours absents. Vérifiez le dossier secrets/.' }
    Write-Host '[OK] Configuration et fichiers secrets vérifiés.' -ForegroundColor Green
}

function Get-GatewayPort {
    $port = '80'
    $line = Select-String -Path '.env' -Pattern '^\s*GATEWAY_PORT\s*=\s*(\d+)' | Select-Object -First 1
    if ($line -and $line.Matches.Count -gt 0) { $port = $line.Matches[0].Groups[1].Value }
    return $port
}

function Get-EnvValue([string]$Name, [string]$Default) {
    $line = Select-String -Path '.env' -Pattern "^\s*$([regex]::Escape($Name))\s*=\s*(.*)$" | Select-Object -First 1
    if ($line -and $line.Matches.Count -gt 0 -and $line.Matches[0].Groups[1].Value.Trim()) { return $line.Matches[0].Groups[1].Value.Trim() }
    return $Default
}

function Test-Url([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec 4 -UseBasicParsing -ErrorAction Stop
        return ($response.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Wait-Url([string]$Url, [int]$Seconds = 90) {
    $until = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $until) {
        if (Test-Url $Url) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Check-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'Docker CLI est introuvable. Installez Docker Desktop pour Windows, ouvrez-le, puis relancez launcher\start.bat.' }
    & docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -ne 0) { Fail 'Le moteur Docker ne répond pas. Ouvrez Docker Desktop, attendez son état « Running », puis relancez launcher\start.bat.' }
    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) { Fail 'Docker Compose v2 est indisponible. Mettez Docker Desktop à jour, puis relancez le script.' }
    Write-Host '[OK] Docker et Docker Compose sont opérationnels.' -ForegroundColor Green
}

function Start-Marketplace {
    Write-Host 'MARCHÉCI — DÉMARRAGE' -ForegroundColor Cyan
    if (-not (Test-Path '.env')) {
        Copy-Item '.env.example' '.env'
        Fail 'Le modèle .env a été créé. Ouvrez .env, remplacez les valeurs CHANGE_ME par vos secrets, enregistrez, puis double-cliquez à nouveau sur launcher\start.bat.'
    }
    Check-Docker
    Invoke-ConfigCheck
    if (-not (Test-Path 'compose.yaml') -or -not (Test-Path 'gateway/nginx.conf')) { Fail 'Fichiers de lancement manquants. Vérifiez que vous êtes dans le dossier complet MarchéCI.' }
    & docker compose -f $ComposeFile config --quiet
    if ($LASTEXITCODE -ne 0) { Fail 'La configuration Docker Compose est invalide. Vérifiez .env et les fichiers du projet.' }
    Write-Host '[OK] Configuration Docker validée. Construction et démarrage des services…' -ForegroundColor Green
    & docker compose -f $ComposeFile up -d --build --wait --wait-timeout 240
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[ERREUR] Au moins un service ne démarre pas. État actuel :' -ForegroundColor Red
        & docker compose -f $ComposeFile ps
        Write-Host 'Consultez les journaux avec launcher\logs.bat.'
        exit 1
    }

    $port = Get-GatewayPort
    $base = "http://localhost:$port"
    $allHealthy = $true
    foreach ($service in $HealthPaths) {
        if (Wait-Url "$base$($service.Path)") {
            Write-Host "[OK] $($service.Name) opérationnel." -ForegroundColor Green
        } else {
            Write-Host "[ÉCHEC] $($service.Name) ne répond pas sur $($service.Path)." -ForegroundColor Red
            $allHealthy = $false
        }
    }
    if (Wait-Url "$base/") { Write-Host '[OK] Frontend accessible.' -ForegroundColor Green }
    else { Write-Host '[ÉCHEC] Frontend inaccessible.' -ForegroundColor Red; $allHealthy = $false }
    if (-not $allHealthy) {
        Write-Host 'Utilisez launcher\status.bat puis launcher\logs.bat pour identifier le service défaillant.' -ForegroundColor Yellow
        exit 1
    }
    Write-Host ''
    Write-Host 'Boutique : ' -NoNewline; Write-Host "$base/" -ForegroundColor Cyan
    Write-Host 'API :      ' -NoNewline; Write-Host "$base/api/" -ForegroundColor Cyan
    Write-Host 'Docs API : ' -NoNewline; Write-Host "$base/docs/catalogue/" -ForegroundColor Cyan
    Write-Host 'Supervision : utilisez launcher\monitoring.bat (facultatif, port 8090).' -ForegroundColor DarkGray
    Write-Host 'STATUT : APPLICATION DÉMARRÉE' -ForegroundColor Green
}

switch ($Action) {
    'start' { Start-Marketplace }
    'stop' {
        Check-Docker
        $monitorIds = & docker compose -f $MonitoringFile ps -q zabbix-web 2>$null
        if ($monitorIds) { & docker compose -f $MonitoringFile down; if ($LASTEXITCODE -ne 0) { Fail 'Arrêt de la supervision incomplet.' } }
        & docker compose -f $ComposeFile down
        if ($LASTEXITCODE -ne 0) { Fail 'Arrêt de MarchéCI incomplet.' }
        Write-Host '[OK] MarchéCI arrêté. Les volumes de données ont été conservés.' -ForegroundColor Green
    }
    'status' {
        Check-Docker
        & docker compose -f $ComposeFile ps
        $port = Get-GatewayPort
        $base = "http://localhost:$port"
        foreach ($service in $HealthPaths) {
            $ok = Test-Url "$base$($service.Path)"
            $label = if ($ok) { 'OPÉRATIONNEL' } else { 'INDISPONIBLE' }
            $color = if ($ok) { 'Green' } else { 'Yellow' }
            Write-Host "[$label] $($service.Name)" -ForegroundColor $color
        }
        $monitorIds = & docker compose -f $MonitoringFile ps -q zabbix-web 2>$null
        if ($monitorIds) { Write-Host "Supervision : http://$(Get-EnvValue 'MON_WEB_BIND' '127.0.0.1'):$(Get-EnvValue 'MON_WEB_PORT' '8090')/" }
    }
    'logs' {
        Check-Docker
        if ($Service -like 'zabbix-*') { & docker compose -f $MonitoringFile logs --tail=100 $Service }
        elseif ($Service) { & docker compose -f $ComposeFile logs --tail=100 $Service }
        else { & docker compose -f $ComposeFile logs --tail=100 }
        if ($LASTEXITCODE -ne 0) { Fail 'Impossible de lire les journaux. Vérifiez le nom du service et son état.' }
    }
    'monitoring' {
        Check-Docker
        Invoke-ConfigCheck
        $zabbixPassword = Get-EnvValue 'ZABBIX_ADMIN_PASSWORD' ''
        if ($zabbixPassword.Length -lt 12 -or $zabbixPassword.StartsWith('CHANGE_ME')) { Fail 'Configurez dans .env un mot de passe ZABBIX_ADMIN_PASSWORD privé de 12 caractères minimum.' }
        $gatewayIds = & docker compose -f $ComposeFile ps -q gateway
        if (-not $gatewayIds) { Fail 'Démarrez MarchéCI avec launcher\start.bat avant la supervision.' }
        & docker compose -f $MonitoringFile config --quiet
        if ($LASTEXITCODE -ne 0) { Fail 'Configuration Zabbix invalide.' }
        & docker compose -f $MonitoringFile up -d --wait --wait-timeout 180
        if ($LASTEXITCODE -ne 0) { Fail 'La pile Zabbix ne démarre pas. Consultez launcher\logs.bat zabbix-web.' }
        $monitorBind = Get-EnvValue 'MON_WEB_BIND' '127.0.0.1'
        if ($monitorBind -in @('0.0.0.0', '::')) { $monitorBind = '127.0.0.1' }
        $monitorPort = Get-EnvValue 'MON_WEB_PORT' '8090'
        $monitorUrl = "http://${monitorBind}:${monitorPort}/"
        $python = Get-PythonCommand
        if (-not $python) { Fail 'Python 3.12+ est nécessaire pour configurer et vérifier les sondes Zabbix.' }
        $env:ZABBIX_API_HOST = $monitorBind
        $env:ZABBIX_API_PORT = $monitorPort
        $env:ZABBIX_API_URL = "http://${monitorBind}:${monitorPort}/api_jsonrpc.php"
        & $python.Exe @($python.Prefix) 'monitoring/zabbix/configure_zabbix_admin.py'
        if ($LASTEXITCODE -ne 0) { Fail 'La configuration du mot de passe administrateur Zabbix a échoué. Consultez launcher\logs.bat zabbix-web.' }
        & $python.Exe @($python.Prefix) 'monitoring/zabbix/provisioning.py' 'verify'
        if ($LASTEXITCODE -ne 0) { Fail 'Le provisionnement ou la collecte Zabbix a échoué. Consultez launcher\logs.bat zabbix-server.' }
        & $python.Exe @($python.Prefix) 'monitoring/zabbix/dashboard.py'
        if ($LASTEXITCODE -ne 0) { Fail 'La création du tableau de bord Zabbix a échoué. Consultez launcher\logs.bat zabbix-web.' }
        if (Wait-Url $monitorUrl 60) { Write-Host "[OK] Zabbix accessible sur $monitorUrl" -ForegroundColor Green }
        else { Fail "Zabbix a démarré mais son interface ne répond pas encore sur $monitorUrl." }
    }
}
