# START-MyDay.ps1 — arranca el stack diario de forma idempotente.
# Lanzado por START-MyDay.bat (doble clic / acceso directo / Startup).
$ErrorActionPreference = 'SilentlyContinue'

function Test-Port([int]$port) {
  [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Start-App([string]$name, [int]$port, [string]$workdir, [string]$file, [string[]]$argList) {
  if (Test-Port $port) {
    Write-Host ("[:{0}] {1} ya esta corriendo, lo dejo." -f $port, $name)
  } else {
    Write-Host ("[:{0}] arrancando {1}..." -f $port, $name)
    Start-Process -FilePath $file -ArgumentList $argList -WorkingDirectory $workdir -WindowStyle Minimized
  }
}

Write-Host '============================================'
Write-Host '  Arrancando tu dia'
Write-Host '  MyDay (:8000) + Transcribe (:8088) + TimeTracker (:8787)'
Write-Host '============================================'
Write-Host ''

# --- TimeTracker: dashboard (:8787) ---
Start-App 'TimeTracker' 8787 'C:\TimeTracker' 'python' @('server.py')

# --- TimeTracker: captura (monitor.py) — evita un segundo monitor (corromperia la DB) ---
$mon = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -like '*monitor.py*' }
if ($mon) {
  Write-Host '[captura] monitor ya activo, lo dejo.'
} else {
  Write-Host '[captura] iniciando monitor...'
  Start-Process -FilePath 'pythonw' -ArgumentList @('monitor.py') -WorkingDirectory 'C:\TimeTracker' -WindowStyle Minimized
}

# --- Transcribe (:8088) — uvicorn directo (sin su .bat) para no abrir su propia pestana ---
Start-App 'Transcribe' 8088 'C:\Transcribe App' 'py' @('-3.13','-m','uvicorn','app:app','--host','127.0.0.1','--port','8088')

# --- MyDay: el cerebro (:8000). main.py carga DATABASE_URL del .env raiz (PostgreSQL). ---
Start-App 'MyDay' 8000 'C:\MyDay\artifacts\myday-python-api' 'C:\MyDay\.venv\Scripts\python.exe' @('-m','uvicorn','main:app','--port','8000')

# --- Esperar a que MyDay responda (hasta ~15s), luego abrir UNA pestana al Command Center ---
Write-Host ''
Write-Host 'Esperando a que MyDay ligue el puerto...'
for ($i = 0; $i -lt 22; $i++) {
  if (Test-Port 8000) { break }
  Start-Sleep -Milliseconds 700
}
Start-Process 'http://localhost:8000/task-manager/command-center'

Write-Host ''
Write-Host 'Listo. Las apps corren en ventanas minimizadas.'
Write-Host 'Para apagar todo: STOP-MyDay.bat'
Start-Sleep -Seconds 3
