param(
  [string]$ComposeFile = ".\docker-compose.yml",
  [Parameter(Mandatory = $true)]
  [string]$QdrantBackup,
  [Parameter(Mandatory = $true)]
  [string]$RedisBackup,
  [string]$QdrantVolume = "",
  [string]$RedisVolume = "",
  [switch]$Force,
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

function Resolve-Or-CreateVolume {
  param(
    [string]$ExplicitName,
    [string]$ShortName,
    [string]$ProjectName
  )

  $name = if ($ExplicitName) { $ExplicitName } else { "${ProjectName}_${ShortName}" }

  if (-not (Test-DockerVolume $name)) {
    Write-Host "Creating Docker volume '$name'..."
    docker volume create $name | Out-Null
  }

  return $name
}

function Restore-Volume {
  param(
    [string]$VolumeName,
    [string]$ArchivePath
  )

  $archive = (Resolve-Path $ArchivePath).Path
  $archiveDir = Split-Path $archive -Parent
  $archiveName = Split-Path $archive -Leaf

  Write-Host "Restoring '$archiveName' -> volume '$VolumeName'"
  docker run --rm `
    -v "${VolumeName}:/data" `
    -v "${archiveDir}:/backup:ro" `
    alpine sh -c "find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar xzf /backup/$archiveName -C /data"
}

if (-not $Force) {
  throw "Restore replaces data inside target volumes. Re-run with -Force only after backing up the target machine."
}

$projectName = Resolve-ProjectName $ComposeFile
$resolvedQdrantVolume = Resolve-Or-CreateVolume -ExplicitName $QdrantVolume -ShortName "qdrant_data" -ProjectName $projectName
$resolvedRedisVolume = Resolve-Or-CreateVolume -ExplicitName $RedisVolume -ShortName "redis_data" -ProjectName $projectName

Write-Host "Stopping RAG services before restore..."
docker compose -f $ComposeFile stop rag-api qdrant redis

Restore-Volume -VolumeName $resolvedQdrantVolume -ArchivePath $QdrantBackup
Restore-Volume -VolumeName $resolvedRedisVolume -ArchivePath $RedisBackup

if (-not $NoRestart) {
  Write-Host "Starting RAG services..."
  docker compose -f $ComposeFile up -d qdrant redis rag-api
}

Write-Host "Restore completed."
