<#
  Normalize duplicate agent YAML paths into canonical Brand Listener root.
  This script targets known duplicates for BrandCultureListeningAgent.yaml and OfficialUpdatesAgent.yaml.
  It moves duplicates to the canonical location under Brand Listener/agents/searcher/
#>

$root = "D:\\wmz\\Brand Listener"  # repository root

function Move-Duplicate {
    param(
        [string]$canonical,
        [string]$dupFilter
    )
    $files = Get-ChildItem -Path $root -Recurse -Filter $dupFilter -File
    foreach ($f in $files) {
        if ($f.FullName -ne $canonical) {
            $destDir = Split-Path -Path $canonical -Parent
            if (-not (Test-Path $destDir)) { New-Item -Path $destDir -ItemType Directory -Force | Out-Null }
            Move-Item -Path $f.FullName -Destination $canonical -Force
        }
    }
}

$canonicalCulture = "$root\\Brand Listener\\agents\\searcher\\BrandCultureListeningAgent.yaml"
$canonicalUpdates = "$root\\Brand Listener\\agents\\searcher\\OfficialUpdatesAgent.yaml"

Move-Duplicate -canonical $canonicalCulture -dupFilter 'BrandCultureListeningAgent.yaml'
Move-Duplicate -canonical $canonicalUpdates -dupFilter 'OfficialUpdatesAgent.yaml'

Write-Output 'Path normalization complete.'
