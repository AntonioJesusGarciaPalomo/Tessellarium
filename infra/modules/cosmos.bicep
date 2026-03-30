// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Cosmos DB (Production)
// Continuous backup with PITR, serverless, private endpoint ready
// ──────────────────────────────────────────────────────────────────────

@description('Name of the Cosmos DB account')
param name string
param location string
param tags object = {}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: name
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [{ locationName: location, failoverPriority: 0 }]
    capabilities: [{ name: 'EnableServerless' }]
    publicNetworkAccess: 'Disabled'
    backupPolicy: {
      type: 'Continuous'
      continuousModeProperties: {
        tier: 'Continuous7Days'
      }
    }
    networkAclBypass: 'AzureServices'
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmos
  name: 'tessellarium'
  properties: {
    resource: { id: 'tessellarium' }
  }
}

resource sessionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'sessions'
  properties: {
    resource: {
      id: 'sessions'
      partitionKey: { paths: ['/id'], kind: 'Hash' }
      defaultTtl: -1
    }
  }
}

resource threadsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'threads'
  properties: {
    resource: {
      id: 'threads'
      partitionKey: { paths: ['/thread_id'], kind: 'Hash' }
    }
  }
}

resource compilationsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'compilations'
  properties: {
    resource: {
      id: 'compilations'
      partitionKey: { paths: ['/session_id'], kind: 'Hash' }
    }
  }
}

output id string = cosmos.id
output endpoint string = cosmos.properties.documentEndpoint
output name string = cosmos.name
