// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Azure Blob Storage (Production)
// Private endpoint ready, HTTPS only
// ──────────────────────────────────────────────────────────────────────

@description('Name of the Storage account')
param name string
param location string
param tags object = {}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: replace(name, '-', '')
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource uploadsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'uploads'
  properties: { publicAccess: 'None' }
}

resource processedContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'processed'
  properties: { publicAccess: 'None' }
}

resource literatureContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'literature'
  properties: { publicAccess: 'None' }
}

output id string = storage.id
output endpoint string = storage.properties.primaryEndpoints.blob
output name string = storage.name
