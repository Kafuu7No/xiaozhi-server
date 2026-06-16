param(
    [string]$Port = "COM10",
    [int]$Baud = 115200,
    [string]$Ssid = "",
    [string]$Password = "",
    [string]$ServerHost = "",
    [string]$BackendUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

function Get-WlanIPv4 {
    $ip = Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "WLAN" -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "169.254*" -and $_.IPAddress -ne "127.0.0.1" } |
        Select-Object -First 1 -ExpandProperty IPAddress
    return $ip
}

function Protect-Arg([string]$Value) {
    if ($null -eq $Value) { return '""' }
    if ($Value -match '[\s"`]') {
        return '"' + ($Value -replace '\\', '\\' -replace '"', '\"') + '"'
    }
    return $Value
}

function ConvertTo-Utf8Hex([string]$Value) {
    if ($null -eq $Value) { return "" }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
    return -join ($bytes | ForEach-Object { $_.ToString("x2") })
}

function Send-Command($PortObj, [string]$Command, [int]$WaitMs = 1500, [string]$DisplayCommand = "", [string]$SensitiveText = "") {
    if ([string]::IsNullOrWhiteSpace($DisplayCommand)) {
        $DisplayCommand = $Command
    }
    Write-Host "=> $DisplayCommand"
    $PortObj.Write("`n")
    Start-Sleep -Milliseconds 400
    for ($i = 0; $i -lt 96; $i++) {
        $PortObj.Write([char]0x08)
        Start-Sleep -Milliseconds 2
    }
    Start-Sleep -Milliseconds 200
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($Command)
    foreach ($byte in $bytes) {
        $PortObj.Write([byte[]]@($byte), 0, 1)
        Start-Sleep -Milliseconds 25
    }
    Start-Sleep -Milliseconds 100
    $PortObj.Write("`n")
    Start-Sleep -Milliseconds $WaitMs
    $output = $PortObj.ReadExisting()
    if ($output) {
        if (![string]::IsNullOrEmpty($SensitiveText)) {
            $output = $output.Replace($SensitiveText, "********")
        }
        Write-Host $output
    }
    return $output
}

if ([string]::IsNullOrWhiteSpace($ServerHost)) {
    $ServerHost = Get-WlanIPv4
}

if ([string]::IsNullOrWhiteSpace($ServerHost)) {
    throw "Cannot find WLAN IPv4 address. Pass -ServerHost manually."
}

if ([string]::IsNullOrWhiteSpace($Ssid)) {
    $Ssid = Read-Host "WiFi SSID"
}

if ([string]::IsNullOrWhiteSpace($Password)) {
    $secure = Read-Host "WiFi password" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $Password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

Write-Host "Using server host: $ServerHost"
Write-Host "Using serial port: $Port @ $Baud"

$serial = [System.IO.Ports.SerialPort]::new($Port, $Baud, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One)
$serial.ReadTimeout = 500
$serial.WriteTimeout = 3000
$serial.Encoding = [System.Text.Encoding]::UTF8
$serial.DtrEnable = $false
$serial.RtsEnable = $false

try {
    $serial.Open()
    Start-Sleep -Seconds 1
    $null = $serial.ReadExisting()

    Send-Command $serial "xz_host $ServerHost" 1200 | Out-Null
    $ssidHex = ConvertTo-Utf8Hex $Ssid
    $passwordHex = ConvertTo-Utf8Hex $Password
    $join = "wifi_join_hex $ssidHex $passwordHex"
    $joinDisplay = "wifi_join_hex $ssidHex ********"
    Send-Command $serial $join 22000 $joinDisplay $Password | Out-Null
    Send-Command $serial "ifconfig" 2000 | Out-Null
    Send-Command $serial "ping $ServerHost" 5000 | Out-Null
}
finally {
    if ($serial.IsOpen) {
        $serial.Close()
    }
}

Write-Host "Checking backend..."
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Seconds 2
    try {
        $sessions = Invoke-RestMethod "$BackendUrl/api/sessions"
        $sensor = Invoke-RestMethod "$BackendUrl/api/sensor/latest"
        Write-Host "sessions:"
        $sessions | ConvertTo-Json -Depth 6 | Write-Host
        Write-Host "latest sensor:"
        $sensor | ConvertTo-Json -Depth 6 | Write-Host
        if ($sessions.sessions.Count -gt 0 -and $sensor.device_id -ne "codex-sim-device") {
            Write-Host "Cloud link looks good."
            exit 0
        }
    }
    catch {
        Write-Host "Backend check failed: $($_.Exception.Message)"
    }
}

Write-Host "No real device session/sensor data yet. Check the serial log above for WiFi or WebSocket errors."
exit 1
