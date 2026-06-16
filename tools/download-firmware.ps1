param(
    [string]$ProjectDir = "D:\Desktop\Edgi_Talk_M55_XiaoZhi_new\Edgi_Talk_M55_XiaoZhi_2\Edgi_Talk_M55_XiaoZhi",
    [string]$OpenOcdRoot = "D:\Desktop\Edgi_Talk_M55_XiaoZhi_new\tools\openocd-5.16.1.4486-windows\openocd"
)

$ErrorActionPreference = "Stop"

$openocd = Join-Path $OpenOcdRoot "bin\openocd.exe"
$scripts = Join-Path $OpenOcdRoot "scripts"
$flm = Join-Path $OpenOcdRoot "flm\infineon\pse8xxgp"
$hex = Join-Path $ProjectDir "Debug\rtthread.hex"

if (!(Test-Path $openocd)) {
    throw "OpenOCD not found: $openocd"
}

if (!(Test-Path $hex)) {
    throw "Firmware hex not found. Build first: $hex"
}

$openocdOutput = & $openocd `
    -s $scripts `
    -s $flm `
    -f "interface/kitprog3.cfg" `
    -c "array set SMIF_BANKS {1 {addr 0x60580000 size 0x00800000 psize 0x1000 esize 0x40000}}" `
    -f "target/infineon/pse84xgxs2.cfg" `
    -c "transport select swd" `
    -c "init; reset init; flash write_image erase $($hex.Replace('\', '/')); reset run; shutdown" 2>&1

$openocdOutput | ForEach-Object { Write-Host $_ }

if ($LASTEXITCODE -ne 0) {
    throw "OpenOCD failed with exit code $LASTEXITCODE"
}

$openocdText = $openocdOutput -join "`n"
if ($openocdText -match "(?m)^Error:|Failed to write memory|timed out while waiting for target halted|error writing to flash") {
    throw "OpenOCD reported a flash programming error"
}
