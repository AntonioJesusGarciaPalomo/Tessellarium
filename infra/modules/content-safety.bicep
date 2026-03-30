@description('Name of the Content Safety resource')
param name string
param location string
param tags object = {}

resource contentSafety 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  kind: 'ContentSafety'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
  }
}

output id string = contentSafety.id
output endpoint string = contentSafety.properties.endpoint
output apiKey string = contentSafety.listKeys().key1
output name string = contentSafety.name
