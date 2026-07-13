param(
  [string]$ComposeFile = ".\docker-compose.yml",
  [string]$BackupDir = ".\backups",
  [string]$QdrantVolume = "",
  [string]$RedisVolume = "",
  [switch]$StopServices,
  [switch]$NoRestart
)

$ErrorActionPreference = "Stop"

function Resolve-ProjectName {
  param([string]$ComposePath)

  $fullPath = (Resolve-Path $ComposePath).Path
  return Split-Path (Split-Path $fullPath -Parent) -Leaf
}

function Test-DockerVolume {
  param([string]$Name)

  docker volume inspect $Name *> $null
  return $LASTEXITCODE -eq 0
}

function Resolve-DockerVolume {
  param(
    [string]$ExplicitName,
    [string]$ShortName,
    [string]$ProjectName
  )

  if ($ExplicitName) {
    if (Test-DockerVolume $ExplicitName) {
      return $ExplicitName
    }
    throw "Volume '$ExplicitName' does not exist."
  }

  $preferred = "${ProjectName}_${ShortName}"
  if (Test-DockerVolume $preferred) {
    return $preferred
  }

  $matches = docker volume ls --format "{{.Name}}" | Where-Object {
    $_ -eq $ShortName -or $_ -like "*_$ShortName"
  }

  if (($matches | Measure-Object).Count -eq 1) {
    return $matches[0]
  }

  if (($matches | Measure-Object).Count -gt 1) {
    throw "Found multiple possible volumes for '$ShortName': $($matches -join ', '). Pass -QdrantVolume or -RedisVolume explicitly."
  }

  throw "Could not find Docker volume for '$ShortName'. Run 'docker volume ls' and pass the exact name."
}

function Backup-Volume {
  param(
    [string]$VolumeName,
    [string]$OutputFile,
    [string]$BackupPath
  )

  Write-Host "Backing up volume '$VolumeName' -> '$OutputFile'"
  docker run --rm `
    -v "${VolumeName}:/data:ro" `
    -v "${BackupPath}:/backup" `
    alpine sh -c "cd /data && tar czf /backup/$OutputFile ."
}

$projectName = Resolve-ProjectName $ComposeFile
$backupPath = (New-Item -ItemType Directory -Force -Path $BackupDir).FullName
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"

$resolvedQdrantVolume = Resolve-DockerVolume -ExplicitName $QdrantVolume -ShortName "qdrant_data" -ProjectName $projectName
$resolvedRedisVolume = Resolve-DockerVolume -ExplicitName $RedisVolume -ShortName "redis_data" -ProjectName $projectName

if ($StopServices) {
  Write-Host "Stopping RAG services for a consistent backup..."
  docker compose -f $ComposeFile stop rag-api qdrant redis
}

try {
  Backup-Volume -VolumeName $resolvedQdrantVolume -OutputFile "qdrant_data_$stamp.tar.gz" -BackupPath $backupPath
  Backup-Volume -VolumeName $resolvedRedisVolume -OutputFile "redis_data_$stamp.tar.gz" -BackupPath $backupPath

  Write-Host ""
  Write-Host "Backup completed:"
  Write-Host "  $backupPath\qdrant_data_$stamp.tar.gz"
  Write-Host "  $backupPath\redis_data_$stamp.tar.gz"
}
finally {
  if ($StopServices -and -not $NoRestart) {
    Write-Host "Restarting RAG services..."
    docker compose -f $ComposeFile up -d qdrant redis rag-api
  }
}
