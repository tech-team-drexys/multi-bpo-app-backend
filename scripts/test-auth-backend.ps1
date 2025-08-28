# test-auth-backend.ps1
# Run in PowerShell. Ajuste variáveis abaixo se necessário.
# Versão corrigida: evita importar modelos que não existem e extrai UUID da saída.
# Inclui correção robusta na etapa de login para lidar com PSCustomObject retornado por Invoke-RestMethod.

# === CONFIG ===
$composeFile = "docker-compose-testes.yml"
$base_url = "http://localhost:5015"
$auth_prefix = "/api/v1/auth"   # use "/api/auth" se for o seu caso
$email = "teste@multibpo.com"
$password = "senha123456"
$whatsapp = "(11) 99999-9999"
$captcha = "demo-token-123"
$backendService = "erp_multibpo_backend"

# ----------------- Auto-detect compose file (resolve relativo/subindo pastas) -----------------
if (-not (Test-Path $composeFile)) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $dir = $scriptDir
    $found = $null
    while ($dir -ne [System.IO.Path]::GetPathRoot($dir) -and -not $found) {
        $candidate = Join-Path $dir $composeFile
        if (Test-Path $candidate) { $found = (Get-Item $candidate).FullName; break }
        $dir = Split-Path $dir -Parent
    }
    if ($found) {
        $composeFile = $found
        Write-Host "Usando docker-compose file encontrado em: $composeFile"
    } else {
        $candidate2 = Join-Path $scriptDir '..\..\'+$composeFile
        try { $resolved2 = Resolve-Path -Path $candidate2 -ErrorAction Stop; $composeFile = $resolved2.Path; Write-Host "Usando docker-compose file (fallback): $composeFile" }
        catch { Write-Error "Arquivo 'docker-compose-testes.yml' não encontrado. Ajuste \$composeFile."; exit 1 }
    }
} else { $composeFile = (Get-Item $composeFile).FullName; Write-Host "Usando docker-compose file (path fornecido): $composeFile" }

# ----------------- Detect docker compose command (v1 vs v2) -----------------
$dcCmdArray = $null
if (Get-Command docker-compose -ErrorAction SilentlyContinue) { $dcCmdArray = @("docker-compose"); Write-Host "Comando Compose detectado: docker-compose" }
elseif (Get-Command docker -ErrorAction SilentlyContinue) {
    try { & docker compose version > $null 2>&1; if ($LASTEXITCODE -eq 0) { $dcCmdArray = @("docker","compose"); Write-Host "Comando Compose detectado: docker compose" } } catch {}
}
if (-not $dcCmdArray) { Write-Error "Não foi possível localizar 'docker-compose' nem 'docker compose' no PATH."; exit 1 }

# ----------------- Função Exec-Compose-Capture -----------------
function Exec-Compose-Capture {
    param([Parameter(Mandatory=$true)][string[]] $cmdParts)
    try {
        if ($dcCmdArray.Length -eq 1) {
            $exe = $dcCmdArray[0]
            $result = & $exe @cmdParts 2>&1
        } else {
            $exe = $dcCmdArray[0]
            $fullArgs = @("compose") + $cmdParts
            $result = & $exe @fullArgs 2>&1
        }
    } catch {
        $result = $_.Exception.Message
    }
    if ($null -eq $result) { return "" }
    if ($result -is [System.Array]) { $out = $result -join "`n" } else { $out = $result.ToString() }
    return $out.Trim()
}

# ----------------- Função Invoke-Api (robusta) -----------------
function Invoke-Api {
    param($method, $path, $body = $null, $headers = $null)
    $uri = "$base_url$path"
    try {
        if ($body -ne $null) {
            $json = $body | ConvertTo-Json -Depth 10
            return Invoke-RestMethod -Uri $uri -Method $method -Headers $headers -Body $json -ContentType "application/json" -ErrorAction Stop
        } else {
            return Invoke-RestMethod -Uri $uri -Method $method -Headers $headers -ErrorAction Stop
        }
    } catch {
        $err = $_
        $msg = $err.Exception.Message
        try {
            if ($err.Exception.Response -ne $null) {
                $resp = $err.Exception.Response
                if ($resp.StatusCode -ne $null) { $msg = "$msg (StatusCode: $($resp.StatusCode.ToString()))" }
                try { $stream = $resp.GetResponseStream(); if ($stream) { $sr = New-Object System.IO.StreamReader($stream); $bodyText = $sr.ReadToEnd(); if ($bodyText) { $msg = "$msg - ResponseBody: $bodyText" } } } catch {}
            }
        } catch {}
        return @{ error = $true; message = $msg; detail = ($err | Out-String) }
    }
}

# ----------------- Regex do UUID -----------------
$uuidPattern = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'

# ----------------- Get-ConfirmationTokenFromDB (apenas User + introspecção) -----------------
function Get-ConfirmationTokenFromDB {
    param($email)
    $py = @"
from django.apps import apps
User = apps.get_model('authentication','User')
u = User.objects.filter(email='$email').first()
if not u:
    print('NOT_FOUND')
else:
    token = getattr(u, 'email_confirmation_token', None)
    if token:
        print(token)
    else:
        # fallback: procurar em modelos do app 'authentication' algum objeto relacionado com campo 'token'
        cfg = apps.get_app_config('authentication')
        found = None
        for m in cfg.get_models():
            try:
                qs = m.objects.filter(user=u)
                if qs.exists():
                    obj = qs.order_by('-id').first()
                    if hasattr(obj, 'token'):
                        print(getattr(obj, 'token'))
                        found = True
                        break
            except Exception:
                pass
        if not found:
            print('NO_TOKEN')
"@
    $cmdParts = @("-f", $composeFile, "exec", "-T", $backendService, "python", "manage.py", "shell", "-c", $py)
    $out = Exec-Compose-Capture -cmdParts $cmdParts
    if ($out -match $uuidPattern) { return $matches[0] }
    if ($out -match "NOT_FOUND") { return "NOT_FOUND" }
    if ($out -match "NO_TOKEN") { return "NO_TOKEN" }
    if ($out -match "^ERR:") { return $out }
    return $out.Trim()
}

# ----------------- Reset-ConfirmationTokenInDB (garante campo ou cria fallback) -----------------
function Reset-ConfirmationTokenInDB {
    param($email)
    $py = @"
from django.apps import apps
import uuid
User = apps.get_model('authentication','User')
u = User.objects.filter(email='$email').first()
if not u:
    print('NOT_FOUND')
else:
    u.email_confirmed = False
    # tentar setar campo em User se existir
    try:
        setattr(u, 'email_confirmation_token', uuid.uuid4())
        u.save()
        print(getattr(u, 'email_confirmation_token'))
    except Exception:
        # fallback: procurar um modelo no app 'authentication' com campo 'token' e criar registro
        cfg = apps.get_app_config('authentication')
        created = False
        for m in cfg.get_models():
            fields = [f.name for f in m._meta.fields]
            if 'user' in fields and 'token' in fields:
                try:
                    inst = m(user=u, token=uuid.uuid4())
                    inst.save()
                    print(inst.token)
                    created = True
                    break
                except Exception:
                    pass
        if not created:
            print('ERR:Could not set token on User or create fallback token model')
"@
    $cmdParts = @("-f", $composeFile, "exec", "-T", $backendService, "python", "manage.py", "shell", "-c", $py)
    $out = Exec-Compose-Capture -cmdParts $cmdParts
    if ($out -match $uuidPattern) { return $matches[0] }
    if ($out -match "NOT_FOUND") { return "NOT_FOUND" }
    return $out.Trim()
}

# ----------------- Início dos testes automatizados -----------------

# === 1) Registro ===
Write-Host "===> 1) Tentando registro do usuário $email ..."
$regBody = @{
    email = $email
    whatsapp = $whatsapp
    password = $password
    password_confirm = $password
    captcha_token = $captcha
    accept_terms = $true
    registration_method = "email"
}
$regResp = Invoke-Api -method Post -path "$auth_prefix/register/" -body $regBody

if ($regResp -is [System.Collections.IDictionary] -and $regResp.Contains("error") -and $regResp.error) {
    Write-Host "[REGISTRO] Erro detectado: $($regResp.message)" -ForegroundColor Yellow
    Write-Host "Tentando resetar token no DB para permitir re-teste..."
    $tokenOut = Reset-ConfirmationTokenInDB -email $email
    if ($tokenOut -match "NOT_FOUND") { Write-Host "Usuário não encontrado no DB. Crie manualmente." -ForegroundColor Red; exit 1 }
    elseif ($tokenOut -match "^ERR:") { Write-Host "Erro ao resetar token no DB: $tokenOut" -ForegroundColor Red; exit 1 }
    else { $confirmationToken = $tokenOut; Write-Host "Token resetado: $confirmationToken" -ForegroundColor Green }
} else {
    Write-Host "[REGISTRO] Sucesso. Resposta (sumário):" -ForegroundColor Green
    try { $regResp | ConvertTo-Json -Depth 5 | Write-Host } catch { Write-Host $regResp }
    # obter token (se não veio no payload)
    $tokenOut = Get-ConfirmationTokenFromDB -email $email
    if ($tokenOut -match "NOT_FOUND|NO_TOKEN|^$|^ERR:") {
        Write-Host "[AVISO] Não consegui ler token automaticamente: $tokenOut" -ForegroundColor Yellow
        Write-Host "Tentando forçar reset do token no DB..."
        $confirmationToken = Reset-ConfirmationTokenInDB -email $email
        if ($confirmationToken -match "ERR:|NOT_FOUND|^$") { Write-Host "Falha ao resetar token: $confirmationToken" -ForegroundColor Red; exit 1 }
        else { Write-Host "Token criado/resetado: $confirmationToken" -ForegroundColor Green }
    } else {
        $confirmationToken = $tokenOut
        Write-Host "Token obtido: $confirmationToken" -ForegroundColor Green
    }
}

if (-not $confirmationToken -or $confirmationToken -match "NOT_FOUND|NO_TOKEN|^ERR:|^\s*$") {
    Write-Host "Token de confirmação inválido ('$confirmationToken'). Pare e verifique manualmente." -ForegroundColor Red
    exit 1
}

# === 2) Confirmar email ===
Write-Host "===> 2) Confirmando email com token: $confirmationToken ..."
$confirmBody = @{ token = $confirmationToken }
$confirmResp = Invoke-Api -method Post -path "$auth_prefix/confirm-email/" -body $confirmBody
if ($confirmResp -is [System.Collections.IDictionary] -and $confirmResp.ContainsKey("error") -and $confirmResp.error) {
    Write-Host "[CONFIRM] Erro: $($confirmResp.message)" -ForegroundColor Red
    exit 1
} else {
    Write-Host "[CONFIRM] OK. Resposta (sumário):" -ForegroundColor Green
    try { $confirmResp | ConvertTo-Json -Depth 5 | Write-Host } catch { Write-Host $confirmResp }
}

# === 3) Login ===
Write-Host "===> 3) Fazendo login para obter tokens JWT ..."
$loginBody = @{ email = $email; password = $password; captcha_token = $captcha }
$loginResp = Invoke-Api -method Post -path "$auth_prefix/login/" -body $loginBody

# ----- CORREÇÃO: usar acesso direto a propriedade (PSCustomObject) em vez de ContainsKey -----
try {
    $access = $null
    $access = $loginResp.access
    if (-not $access) { throw "No access token returned" }
    $refresh = $loginResp.refresh
    Write-Host "[LOGIN] Success. Access token length: $($access.Length)" -ForegroundColor Green
} catch {
    Write-Host "[LOGIN] Falha. Resposta (detalhe):" -ForegroundColor Red
    try { $loginResp | ConvertTo-Json -Depth 5 | Write-Host } catch { Write-Host $loginResp }
    exit 1
}

$headers = @{ Authorization = "Bearer $access"; "Content-Type" = "application/json" }

# === 4) GET PROFILE ===
Write-Host "===> 4) GET /profile/ ..."
$profile = Invoke-Api -method Get -path "$auth_prefix/profile/" -headers $headers
if ($profile -and -not ($profile.error)) { Write-Host "[PROFILE] OK. Dados (sumário):" -ForegroundColor Green; try { $profile | ConvertTo-Json -Depth 5 | Write-Host } catch { Write-Host $profile } }
else { Write-Host "[PROFILE] Falha (detalhe):" -ForegroundColor Red; try { $profile | ConvertTo-Json -Depth 5 | Write-Host } catch { Write-Host $profile } }

# === 5) LUCA status (logado) ===
Write-Host "===> 5) GET /luca/status/ (logado) ..."
$status = Invoke-Api -method Get -path "$auth_prefix/luca/status/" -headers $headers
Write-Host "[LUCA STATUS] Resposta (sumário):" -ForegroundColor Cyan
try { $status | ConvertTo-Json -Depth 5 | Write-Host } catch { Write-Host $status }

# === 6) LUCA anônimo (limite 4) ===
Write-Host "===> 6) LUCA anônimo: enviar 5 perguntas para verificar limite (4 permitidas) ..."
$sessionId = [guid]::NewGuid().ToString()
for ($i=1; $i -le 5; $i++) {
    $qBody = @{ question = "Pergunta de teste $i - hora $(Get-Date -Format o)"; session_id = $sessionId }
    $qresp = Invoke-Api -method Post -path "$auth_prefix/luca/question/" -body $qBody
    if ($qresp -and -not ($qresp.error)) {
        Write-Host "[LUCA-ANON][$i] OK - resposta curta:" -NoNewline
        try { if ($qresp.ContainsKey("answer")) { Write-Host " $($qresp.answer.ToString().Substring(0,[Math]::Min(80,$qresp.answer.ToString().Length)))..." } else { Write-Host " (sem campo answer visível)" } } catch { Write-Host " (resposta não exibível)" }
    } else {
        Write-Host "[LUCA-ANON][$i] ERRO/LIMIT? ->" -ForegroundColor Yellow
        try { $qresp | ConvertTo-Json -Depth 5 | Write-Host } catch { Write-Host $qresp }
    }
    Start-Sleep -Seconds 1
}

# === 7) LUCA logado ===
Write-Host "===> 7) LUCA logado: enviar 2 perguntas (contador por usuário) ..."
for ($i=1; $i -le 2; $i++) {
    $qBody = @{ question = "Pergunta logada $i - hora $(Get-Date -Format o)" }
    $qresp = Invoke-Api -method Post -path "$auth_prefix/luca/question/" -body $qBody -headers $headers
    if ($qresp -and -not ($qresp.error)) {
        Write-Host "[LUCA-LOG][$i] OK - resposta curta:" -NoNewline
        try { if ($qresp.ContainsKey("answer")) { Write-Host " $($qresp.answer.ToString().Substring(0,[Math]::Min(80,$qresp.answer.ToString().Length)))..." } else { Write-Host " (sem campo answer visível)" } } catch { Write-Host " (resposta não exibível)" }
    } else {
        Write-Host "[LUCA-LOG][$i] ERRO ->" -ForegroundColor Red
        try { $qresp | ConvertTo-Json -Depth 5 | Write-Host } catch { Write-Host $qresp }
    }
    Start-Sleep -Seconds 1
}

Write-Host "`n====== FINISHED: Testes automáticos completos ======" -ForegroundColor Green
if ($access) { Write-Host "Access token preview (primeiros 100 chars):"; Write-Host $access.Substring(0,[Math]::Min(100,$access.Length)) }
else { Write-Host "Nenhum access token disponível para exibir." }
