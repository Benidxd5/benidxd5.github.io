$DescriptionURL = "https://github.com/Benidxd5/benidxd5.github.io"
$AzureKeyVaultTenantId = "e21ebe2c-3b5b-4d4c-8d0e-c1ca0e8ea14b"
$TimestampService = "http://timestamp.digicert.com"

$AzureKeyVaultURL = "https://cloudflight-code-signing.vault.azure.net"
$AzureKeyVaultClientId = "18462f44-aee3-42ac-aba8-bdfd3d4d8c23"
$AzureKeyVaultClientSecret = "$env:AZURE_SIGN_CLIENT_SECRET"
$AzureKeyVaultCertificate = "globalsign-ev-code-signing"

& dotnet tool restore
& dotnet tool run azuresigntool sign `
    -du "$DescriptionURL" `
    -fd sha256 `
    -kvu "$AzureKeyVaultURL" `
    -kvi "$AzureKeyVaultClientId" `
    -kvt "$AzureKeyVaultTenantId" `
    -kvs "$AzureKeyVaultClientSecret" `
    -kvc "$AzureKeyVaultCertificate" `
    -tr "$TimestampService" `
    -td sha384 `
    -v `
    "$PSScriptRoot\source.msix"
