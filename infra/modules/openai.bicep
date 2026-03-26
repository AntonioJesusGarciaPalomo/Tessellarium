@description('Name of the Azure OpenAI resource')
param name string
param location string
param tags object = {}
param gpt4oDeploymentName string = 'gpt-4o'
param gpt4oMiniDeploymentName string = 'gpt-4o-mini'

resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
  }
}

resource gpt4o 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: gpt4oDeploymentName
  sku: { name: 'GlobalStandard', capacity: 30 }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-4o', version: '2024-11-20' }
  }
}

resource gpt4oMini 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: gpt4oMiniDeploymentName
  sku: { name: 'GlobalStandard', capacity: 30 }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-4o-mini', version: '2024-07-18' }
  }
  dependsOn: [gpt4o]
}

output endpoint string = openai.properties.endpoint
output apiKey string = openai.listKeys().key1
output name string = openai.name
