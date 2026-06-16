param(
    [string]$ProjectDir = "D:\Desktop\Edgi_Talk_M55_XiaoZhi_new\Edgi_Talk_M55_XiaoZhi_2\Edgi_Talk_M55_XiaoZhi",
    [string]$StudioDir = "E:\RT-ThreadStudio",
    [string]$WifiSsid = "",
    [string]$WifiPassword = "",
    [string]$ServerHost = ""
)

$ErrorActionPreference = "Stop"

$scons = Join-Path $StudioDir "platform\env_released\env\tools\Python27\Scripts\scons.bat"
$python27 = Join-Path $StudioDir "platform\env_released\env\tools\Python27"
$gccBin = Join-Path $StudioDir "platform\env_released\env\tools\gnu_gcc\arm_gcc\mingw\bin"
$downloadScript = Join-Path $PSScriptRoot "download-firmware.ps1"

if (!(Test-Path $scons)) {
    throw "SCons not found: $scons"
}

if (!(Test-Path (Join-Path $gccBin "arm-none-eabi-gcc.exe"))) {
    throw "ARM GCC not found: $gccBin"
}

$env:RTT_EXEC_PATH = $gccBin
$env:Path = "$((Join-Path $python27 'Scripts'));$python27;$gccBin;$env:Path"

function Write-WifiProvisionHeader {
    param(
        [string]$Path,
        [string]$SsidHex,
        [string]$PasswordHex
    )

    $content = @"
#ifndef __WIFI_PROVISION_CONFIG_H__
#define __WIFI_PROVISION_CONFIG_H__

#define XZ_WIFI_PROVISION_SSID_HEX      "$SsidHex"
#define XZ_WIFI_PROVISION_PASSWORD_HEX  "$PasswordHex"

#endif /* __WIFI_PROVISION_CONFIG_H__ */
"@

    Set-Content -Path $Path -Value $content -Encoding ASCII
}

function Write-XiaoZhiLocalConfig {
    param(
        [string]$Path,
        [string]$ServerHost
    )

    $hostDefine = ""
    if (![string]::IsNullOrEmpty($ServerHost)) {
        $escapedServerHost = $ServerHost.Replace('\', '\\').Replace('"', '\"')
        $hostDefine = "#define XIAOZHI_HOST `"$escapedServerHost`""
    }

    $content = @"
#ifndef __XIAOZHI_LOCAL_CONFIG_H__
#define __XIAOZHI_LOCAL_CONFIG_H__

$hostDefine

#endif /* __XIAOZHI_LOCAL_CONFIG_H__ */
"@

    Set-Content -Path $Path -Value $content -Encoding ASCII
}

$provisionHeader = Join-Path $ProjectDir "applications\xiaozhi\webnet\wifi_provision_config.h"
$localConfigHeader = Join-Path $ProjectDir "applications\xiaozhi\xiaozhi_local_config.h"

if (![string]::IsNullOrEmpty($WifiSsid)) {
    $ssidHex = -join ([System.Text.Encoding]::UTF8.GetBytes($WifiSsid) | ForEach-Object { $_.ToString("x2") })
    $passwordHex = -join ([System.Text.Encoding]::UTF8.GetBytes($WifiPassword) | ForEach-Object { $_.ToString("x2") })
    Write-WifiProvisionHeader -Path $provisionHeader -SsidHex $ssidHex -PasswordHex $passwordHex
    Remove-Item Env:\RTT_EXTRA_CFLAGS -ErrorAction SilentlyContinue
    Write-Host "Embedding WiFi SSID: $WifiSsid"
}
else {
    Write-Host "Keeping existing WiFi provision header: $provisionHeader"
}

if (![string]::IsNullOrEmpty($ServerHost)) {
    Write-XiaoZhiLocalConfig -Path $localConfigHeader -ServerHost $ServerHost
    Remove-Item Env:\RTT_EXTRA_CFLAGS -ErrorAction SilentlyContinue
    Write-Host "Embedding XiaoZhi server host: $ServerHost"
}
else {
    Remove-Item Env:\RTT_EXTRA_CFLAGS -ErrorAction SilentlyContinue
    Write-Host "Keeping existing XiaoZhi server host header: $localConfigHeader"
}

Push-Location $ProjectDir
try {
    & $scons -j8
    if ($LASTEXITCODE -ne 0) {
        throw "SCons build failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

& $downloadScript -ProjectDir $ProjectDir
