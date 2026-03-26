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
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmos
  name: 'tessellarium'
  properties: {
    resource: { id: 'tessellarium' }
  }
}

resource container 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'sessions'
  properties: {
    resource: {
      id: 'sessions'
      partitionKey: { paths: ['/id'], kind: 'Hash' }
    }
  }
}

output endpoint string = cosmos.properties.documentEndpoint
output key string = cosmos.listKeys().primaryMasterKey
output name string = cosmos.name
