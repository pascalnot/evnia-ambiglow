# Records ~6 s of USB traffic with Windows' built-in USB ETW tracing (needs admin),
# while Windows Dynamic Lighting drives the Ambiglow, so we can see the exact
# LampArray packets the monitor accepts. Writes usbtrace.etl + usbtrace.xml here.
Set-Location $PSScriptRoot
Start-Transcript -Path (Join-Path $PSScriptRoot "capture.log") -Force | Out-Null
$etl = Join-Path $PSScriptRoot "usbtrace.etl"
$xml = Join-Path $PSScriptRoot "usbtrace.xml"

Write-Host ""
Write-Host "1) Settings > Personalization > Dynamic Lighting: turn ON 'Use Dynamic Lighting on my devices'"
Write-Host "2) Pick the Evnia, set the effect to Rainbow (or Wave) so the LEDs are moving"
Read-Host "3) Press Enter when the rainbow is running"

cmd /c "logman stop usbtrace -ets >nul 2>&1 & logman delete usbtrace >nul 2>&1"
# USBXHCI + UCX, all keywords, verbose
$pf = Join-Path $PSScriptRoot "usbproviders.txt"
@(
    '{30E1D284-5D88-459C-83FD-6345B39B19EC} 0xFFFFFFFFFFFFFFFF 0xFF',
    '{36DA592D-E43A-4E28-AF6F-4BC57C5A11E8} 0xFFFFFFFFFFFFFFFF 0xFF'
) | Set-Content -Encoding Ascii $pf
logman start usbtrace -ets -o $etl -pf $pf -nb 128 640 -bs 128
Write-Host "Capturing for 6 seconds..."
Start-Sleep -Seconds 6
logman stop usbtrace -ets

$found = Get-ChildItem (Join-Path $PSScriptRoot "usbtrace*.etl") | Select-Object -First 1
Write-Host "Converting $found ..."
tracerpt "$($found.FullName)" -o "$xml" -of XML -y
Stop-Transcript | Out-Null
Write-Host ""
Write-Host "Done: $xml ($([math]::Round((Get-Item $xml).Length / 1MB, 1)) MB)"
Write-Host "You can turn Dynamic Lighting off again. Press Enter to close."
Read-Host
