// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Agent-Dedicated Stores
//
// Separate storage resources for Foundry Agent Service:
// - Storage account (agent file uploads, Code Interpreter sandbox)
// - Cosmos DB (BYO thread storage)
// - AI Search (Foundry IQ knowledge base index)
// - Key Vault (agent secrets, MCP tokens)
// ──────────────────────────────────────────────────────────────────────

@description('Name token for agent store resources')
param name string
param location string
param tags object = {}

// ─── Agent Storage Account ──────────────────────────────────────────

resource agentStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: replace('stag${name}', '-', '')
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource agentBlobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: agentStorage
  name: 'default'
}

resource agentFilesContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: agentBlobService
  name: 'agent-files'
  properties: { publicAccess: 'None' }
}

resource agentSandboxContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: agentBlobService
  name: 'code-interpreter'
  properties: { publicAccess: 'None' }
}

// ─── Agent Cosmos DB ────────────────────────────────────────────────

resource agentCosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: 'cosmos-ag-${name}'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [{ locationName: location, failoverPriority: 0 }]
    capabilities: [{ name: 'EnableServerless' }]
  }
}

resource agentDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: agentCosmos
  name: 'tessellarium-agents'
  properties: {
    resource: { id: 'tessellarium-agents' }
  }
}

resource agentThreadsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: agentDatabase
  name: 'threads'
  properties: {
    resource: {
      id: 'threads'
      partitionKey: { paths: ['/thread_id'], kind: 'Hash' }
    }
  }
}

resource agentRunsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: agentDatabase
  name: 'runs'
  properties: {
    resource: {
      id: 'runs'
      partitionKey: { paths: ['/run_id'], kind: 'Hash' }
    }
  }
}

// ─── Agent AI Search ────────────────────────────────────────────────

resource agentSearch 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: 'srch-ag-${name}'
  location: location
  tags: tags
  sku: { name: 'basic' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    semanticSearch: 'standard'
  }
}

// ─── Agent Key Vault ────────────────────────────────────────────────

resource agentKeyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: take('kvag${replace(name, '-', '')}', 24)
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

// ─── Outputs ────────────────────────────────────────────────────────

output storageId string = agentStorage.id
output storageName string = agentStorage.name
output storageEndpoint string = agentStorage.properties.primaryEndpoints.blob

output cosmosId string = agentCosmos.id
output cosmosName string = agentCosmos.name
output cosmosEndpoint string = agentCosmos.properties.documentEndpoint

output searchId string = agentSearch.id
output searchName string = agentSearch.name
output searchEndpoint string = 'https://${agentSearch.name}.search.windows.net'

output keyVaultId string = agentKeyVault.id
output keyVaultName string = agentKeyVault.name
output keyVaultUri string = agentKeyVault.properties.vaultUri
