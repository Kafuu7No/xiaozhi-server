# Download funasr/paraformer-zh from hf-mirror with resume + retry (flaky network).
$base = "https://hf-mirror.com/funasr/paraformer-zh/resolve/main"
$dest = "D:\Desktop\Edgi_Talk_M55_XiaoZhi_new\xiaozhi-server\models\paraformer-zh"
New-Item -ItemType Directory -Force "$dest\example" | Out-Null
$files = @("config.yaml", "configuration.json", "am.mvn", "tokens.json", "seg_dict", "example/asr_example.wav", "model.pt")
foreach ($f in $files) {
    $out = Join-Path $dest ($f -replace '/', '\')
    $ok = $false
    for ($i = 1; $i -le 60 -and -not $ok; $i++) {
        & curl.exe -L -sS -C - --connect-timeout 20 --speed-time 40 --speed-limit 500 -o $out "$base/$f"
        $code = $LASTEXITCODE
        if ($code -eq 0) { $ok = $true }
        elseif ($code -eq 33 -and (Test-Path $out) -and (Get-Item $out).Length -gt 0) {
            # 416 range-not-satisfiable: file already complete
            $ok = $true
        }
        else {
            Write-Output "retry ${i}: $f (curl exit $code, have $(if (Test-Path $out) { (Get-Item $out).Length } else { 0 }) bytes)"
            Start-Sleep 3
        }
    }
    if (-not $ok) { Write-Output "FAILED: $f"; exit 1 }
    Write-Output "OK: $f -> $((Get-Item $out).Length) bytes"
}
Write-Output "ALL DONE"
