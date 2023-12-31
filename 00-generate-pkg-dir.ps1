param (
    $path
)

$parts = $path.Split("/")

$parts = $parts[0..($parts.Length-2)]

$fileName = $path.Split("/")[-1]

$dirpath = $parts -join "/"

$dirpath = "packages/" + $dirpath

#removes any files in directory
if(Test-Path $dirpath){
    $files = Get-ChildItem $dirpath

    foreach ($file in $files) {
        Remove-Item $file.FullName -Force
    }
}

$null = New-Item -Path $dirpath -Force -ItemType Directory

$filePath = (Join-Path -Path $dirpath -ChildPath $fileName)

$null = New-Item -Path $filePath -Force -ItemType File

return [string]$filePath