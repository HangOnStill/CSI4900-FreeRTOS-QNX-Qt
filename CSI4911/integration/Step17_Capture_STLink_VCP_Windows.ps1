# CSI4900 bounded binary STM32 LPUART1 capture from Windows ST-LINK virtual COM.
# This is read-only serial capture: no writes, no firmware flash, no STM32/QNX GPIO changes.
# Requires actual board present and correctly routed UART. NOT run during source preparation.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^COM[1-9][0-9]*$')]
    [string]$Port,
    [ValidateRange(1,120)]
    [int]$Seconds=15,
    [ValidateRange(1,8388608)]
    [int]$MaxBytes=1048576
)
$ErrorActionPreference='Stop'
$ports=@([System.IO.Ports.SerialPort]::GetPortNames())
if($ports -notcontains $Port) {
    throw "Serial port not available. Requested $Port; detected: $($ports -join ', ')"
}
$root=(Get-Item -LiteralPath $PSScriptRoot).Parent.Parent.Parent.Parent.FullName
$outputRoot=Join-Path $root 'evidence\Step17_STLink_Captures'
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$runDir=Join-Path $outputRoot ("stlink_"+$Port+"_"+$stamp)
New-Item -ItemType Directory -Path $runDir -ErrorAction Stop|Out-Null
$raw=Join-Path $runDir 'capture.bin'
$record=Join-Path $runDir 'manifest.json'
$portObject=New-Object System.IO.Ports.SerialPort($Port,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$portObject.ReadTimeout=300
$portObject.WriteTimeout=300
$portObject.Handshake=[System.IO.Ports.Handshake]::None
$portObject.DtrEnable=$false
$portObject.RtsEnable=$false
$buffer=New-Object 'byte[]' 4096
$bytes=0
$errors=0
$start=[DateTime]::UtcNow
$fs=$null
$opened=$false
try {
    $fs=[System.IO.File]::Open($raw,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write)
    $portObject.Open()
    $opened=$true
    $stop=[DateTime]::UtcNow.AddSeconds($Seconds)
    while(([DateTime]::UtcNow -lt $stop) -and ($bytes -lt $MaxBytes)) {
        $remaining=[Math]::Min($buffer.Length,$MaxBytes-$bytes)
        try {
            $count=$portObject.Read($buffer,0,$remaining)
            if($count -gt 0) {
                $fs.Write($buffer,0,$count)
                $bytes+=$count
            }
        } catch [System.TimeoutException] {
            # Normal: wait for another serial receive window without sending data.
        }
    }
}
catch {
    $errors++
    Write-Warning ("Capture error: "+$_.Exception.Message)
}
finally {
    if($opened){$portObject.Close()}
    $portObject.Dispose()
    if($null -ne $fs){$fs.Flush();$fs.Dispose()}
}
$status=if($errors -gt 0){'CAPTURE_ERROR'}elseif($bytes -eq 0){'NO_DATA'}else{'CAPTURED_UNVALIDATED'}
$hash=if(Test-Path $raw){(Get-FileHash -Algorithm SHA256 -LiteralPath $raw).Hash}else{$null}
$manifest=[ordered]@{
    status=$status
    source='WINDOWS_STLINK_VCP_BINARY_READ_ONLY'
    provenance='captured_not_verified_against_firmware'
    target_protocol='STM32L5 LPUART1 wire v1 (unconfirmed)'
    port=$Port
    baud=115200
    data_bits=8
    parity='none'
    stop_bits=1
    read_only=$true
    duration_seconds_requested=$Seconds
    max_bytes=$MaxBytes
    bytes_received=$bytes
    started_utc=$start.ToString('o')
    ended_utc=[DateTime]::UtcNow.ToString('o')
    raw_sha256=$hash
    actual_source_clock_hz='UNKNOWN'
    firmware_commit='UNKNOWN'
    board_solder_bridges='UNVERIFIED'
    crc_check='NOT_RUN'
    real_qnx_uart_capture=$false
}
$manifest|ConvertTo-Json -Depth 5 |Set-Content -LiteralPath $record -Encoding UTF8
Write-Output ("CAPTURE_STATUS="+$status)
Write-Output ("CAPTURE_BYTES="+$bytes)
Write-Output ("RAW_FILE="+$raw)
Write-Output ("RAW_SHA256="+$hash)
Write-Output ("MANIFEST="+$record)
Write-Output "Do not infer 16 cycles/us until the actual firmware clock is measured."
if($errors -gt 0){exit 2}
if($bytes -eq 0){exit 3}
exit 0
