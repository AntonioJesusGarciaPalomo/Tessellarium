// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Azure OpenAI (Production)
// ──────────────────────────────────────────────────────────────────────

@description('Name of the Azure OpenAI resource')
param name string
param location string
param tags object = {}
param gpt4oDeploymentName string = 'gpt-4o'
param gpt4oMiniDeploymentName string = 'gpt-4o-mini'
param gpt41DeploymentName string = 'gpt-4.1'
param gpt41MiniDeploymentName string = 'gpt-4.1-mini'
param embeddingDeploymentName string = 'text-embedding-3-large'

resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
    }
  }
}

// ─── Model Deployments ──────────────────────────────────────────────

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

resource gpt41 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: gpt41DeploymentName
  sku: { name: 'GlobalStandard', capacity: 30 }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-4.1', version: '2025-04-14' }
  }
  dependsOn: [gpt4oMini]
}

resource gpt41Mini 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: gpt41MiniDeploymentName
  sku: { name: 'GlobalStandard', capacity: 30 }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-4.1-mini', version: '2025-04-14' }
  }
  dependsOn: [gpt41]
}

resource embedding 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: embeddingDeploymentName
  sku: { name: 'Standard', capacity: 30 }
  properties: {
    model: { format: 'OpenAI', name: 'text-embedding-3-large', version: '1' }
  }
  dependsOn: [gpt41Mini]
}

// ─── Outputs ────────────────────────────────────────────────────────

output id string = openai.id
output endpoint string = openai.properties.endpoint
output name string = openai.name
