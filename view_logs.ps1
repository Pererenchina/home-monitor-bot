# Скрипт для просмотра логов бота
param(
    [int]$Lines = 50,
    [switch]$Follow,
    [switch]$Errors
)

$logFile = "logs\bot.log"

if (-not (Test-Path $logFile)) {
    Write-Host "Файл логов не найден: $logFile" -ForegroundColor Red
    Write-Host "Бот еще не создал файл логов или не запущен." -ForegroundColor Yellow
    exit
}

if ($Errors) {
    Write-Host "`n=== ПОСЛЕДНИЕ ОШИБКИ ===" -ForegroundColor Red
    Get-Content $logFile -Tail 200 | Select-String "ERROR" | Select-Object -Last $Lines
} elseif ($Follow) {
    Write-Host "Отслеживание логов в реальном времени (Ctrl+C для выхода)..." -ForegroundColor Green
    Get-Content $logFile -Wait -Tail $Lines
} else {
    Write-Host "`n=== ПОСЛЕДНИЕ $Lines СТРОК ЛОГОВ ===" -ForegroundColor Green
    Get-Content $logFile -Tail $Lines
}
