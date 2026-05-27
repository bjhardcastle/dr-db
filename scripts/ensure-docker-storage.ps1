$ErrorActionPreference = "Stop"

$root = if ($env:DR_DB_STORAGE_ROOT) {
    $env:DR_DB_STORAGE_ROOT
} else {
    "\\allen\ai\homedirs\ben.hardcastle\dr-db"
}

$directories = @(
    "",
    "postgres",
    "mathesar",
    "mathesar\static",
    "mathesar\media",
    "mathesar\secrets",
    "mathesar\caddy"
)

foreach ($relativePath in $directories) {
    $path = if ($relativePath) {
        Join-Path -Path $root -ChildPath $relativePath
    } else {
        $root
    }

    if (Test-Path -LiteralPath $path -PathType Leaf) {
        throw "Refusing to continue because '$path' exists and is a file."
    }

    if (Test-Path -LiteralPath $path -PathType Container) {
        Write-Host "Exists:  $path"
        continue
    }

    New-Item -ItemType Directory -Path $path | Out-Null
    Write-Host "Created: $path"
}
