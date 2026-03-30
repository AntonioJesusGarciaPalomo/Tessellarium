// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Azure Infrastructure (Production)
// Decisive Experiment Compiler
//
// VNet with private endpoints, Front Door Premium + WAF,
// Container Apps in workload profiles mode, Foundry project,
// separate agent-dedicated stores, managed identity auth.
// ──────────────────────────────────────────────────────────────────────

targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (e.g., dev, staging, prod)')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string = 'swedencentral'

@description('GPT-4o deployment name')
param gpt4oDeploymentName string = 'gpt-4o'
@description('GPT-4o-mini deployment name')
param gpt4oMiniDeploymentName string = 'gpt-4o-mini'
@description('GPT-4.1 deployment name')
param gpt41DeploymentName string = 'gpt-4.1'
@description('GPT-4.1-mini deployment name')
param gpt41MiniDeploymentName string = 'gpt-4.1-mini'

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName, project: 'tessellarium' }

// ═══════════════════════════════════════════════════════════════════════
// RESOURCE GROUP
// ═══════════════════════════════════════════════════════════════════════

resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: '${abbrs.resourceGroup}tessellarium-${environmentName}'
  location: location
  tags: tags
}

// ═══════════════════════════════════════════════════════════════════════
// NETWORKING
// ═══════════════════════════════════════════════════════════════════════

module network './modules/network.bicep' = {
  name: 'network'
  scope: rg
  params: {
    name: resourceToken
    location: location
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════════════════════
// APPLICATION SERVICES
// ═══════════════════════════════════════════════════════════════════════

module openai './modules/openai.bicep' = {
  name: 'openai'
  scope: rg
  params: {
    name: '${abbrs.cognitiveServicesAccount}${resourceToken}'
    location: location
    tags: tags
    gpt4oDeploymentName: gpt4oDeploymentName
    gpt4oMiniDeploymentName: gpt4oMiniDeploymentName
    gpt41DeploymentName: gpt41DeploymentName
    gpt41MiniDeploymentName: gpt41MiniDeploymentName
  }
}

module contentSafety './modules/content-safety.bicep' = {
  name: 'content-safety'
  scope: rg
  params: {
    name: '${abbrs.cognitiveServicesAccount}safety-${resourceToken}'
    location: location
    tags: tags
  }
}

module search './modules/search.bicep' = {
  name: 'search'
  scope: rg
  params: {
    name: '${abbrs.searchService}${resourceToken}'
    location: location
    tags: tags
  }
}

module cosmos './modules/cosmos.bicep' = {
  name: 'cosmos'
  scope: rg
  params: {
    name: '${abbrs.cosmosDBAccount}${resourceToken}'
    location: location
    tags: tags
  }
}

module storage './modules/storage.bicep' = {
  name: 'storage'
  scope: rg
  params: {
    name: '${abbrs.storageAccount}${resourceToken}'
    location: location
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════════════════════
// AGENT-DEDICATED STORES
// ═══════════════════════════════════════════════════════════════════════

module agentStores './modules/agent-stores.bicep' = {
  name: 'agent-stores'
  scope: rg
  params: {
    name: resourceToken
    location: location
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════════════════════
// CONTAINER REGISTRY (separate to break circular dependency)
// ═══════════════════════════════════════════════════════════════════════

module acr './modules/acr.bicep' = {
  name: 'acr'
  scope: rg
  params: {
    name: '${abbrs.containerRegistry}${resourceToken}'
    location: location
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════════════════════
// CONTAINER APPS
// ═══════════════════════════════════════════════════════════════════════

module containerApps './modules/container-apps.bicep' = {
  name: 'container-apps'
  scope: rg
  params: {
    name: '${abbrs.containerAppsEnvironment}${resourceToken}'
    location: location
    tags: tags
    subnetId: network.outputs.snetAppAcaId
    appIdentityId: identity.outputs.appIdentityId
    acrLoginServer: acr.outputs.loginServer
    openaiEndpoint: openai.outputs.endpoint
    contentSafetyEndpoint: contentSafety.outputs.endpoint
    searchEndpoint: search.outputs.endpoint
    cosmosEndpoint: cosmos.outputs.endpoint
    storageEndpoint: storage.outputs.endpoint
    foundryEndpoint: foundry.outputs.projectEndpoint
    foundryProject: foundry.outputs.projectName
  }
}

// ═══════════════════════════════════════════════════════════════════════
// FOUNDRY PROJECT
// ═══════════════════════════════════════════════════════════════════════

module foundry './modules/foundry.bicep' = {
  name: 'foundry'
  scope: rg
  params: {
    name: resourceToken
    location: location
    tags: tags
    identityId: identity.outputs.foundryIdentityId
    openaiAccountId: openai.outputs.id
    searchAccountId: agentStores.outputs.searchId
    storageAccountId: agentStores.outputs.storageId
    cosmosAccountId: agentStores.outputs.cosmosId
    keyVaultId: agentStores.outputs.keyVaultId
  }
}

// ═══════════════════════════════════════════════════════════════════════
// MANAGED IDENTITIES & RBAC
// ═══════════════════════════════════════════════════════════════════════

module identity './modules/identity.bicep' = {
  name: 'identity'
  scope: rg
  params: {
    name: resourceToken
    location: location
    tags: tags
    acrId: acr.outputs.id
    cosmosAppAccountId: cosmos.outputs.id
    cosmosAppAccountName: cosmos.outputs.name
    cosmosAgentAccountId: agentStores.outputs.cosmosId
    cosmosAgentAccountName: agentStores.outputs.cosmosName
    storageAppAccountId: storage.outputs.id
    storageAgentAccountId: agentStores.outputs.storageId
    openaiAccountId: openai.outputs.id
    searchAppId: search.outputs.id
    searchAgentId: agentStores.outputs.searchId
    keyVaultAppId: agentStores.outputs.keyVaultId
    keyVaultAgentId: agentStores.outputs.keyVaultId
  }
}

// ═══════════════════════════════════════════════════════════════════════
// STATIC WEB APP (Frontend)
// ═══════════════════════════════════════════════════════════════════════

module staticWebApp './modules/static-web-app.bicep' = {
  name: 'static-web-app'
  scope: rg
  params: {
    name: '${abbrs.staticWebApp}${resourceToken}'
    location: location
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════════════════════
// FRONT DOOR + WAF
// ═══════════════════════════════════════════════════════════════════════

module frontDoor './modules/front-door.bicep' = {
  name: 'front-door'
  scope: rg
  params: {
    name: resourceToken
    tags: tags
    backendFqdn: containerApps.outputs.apiFqdn
  }
}

// ═══════════════════════════════════════════════════════════════════════
// PRIVATE ENDPOINTS — Application Services
// ═══════════════════════════════════════════════════════════════════════

module peCosmosApp './modules/private-endpoint.bicep' = {
  name: 'pe-cosmos-app'
  scope: rg
  params: {
    name: 'pe-cosmos-app-${resourceToken}'
    location: location
    tags: tags
    subnetId: network.outputs.snetAppPeId
    privateLinkServiceId: cosmos.outputs.id
    groupId: 'Sql'
    privateDnsZoneId: network.outputs.dnsZoneIds.cosmos
  }
}

module peStorageApp './modules/private-endpoint.bicep' = {
  name: 'pe-storage-app'
  scope: rg
  params: {
    name: 'pe-storage-app-${resourceToken}'
    location: location
    tags: tags
    subnetId: network.outputs.snetAppPeId
    privateLinkServiceId: storage.outputs.id
    groupId: 'blob'
    privateDnsZoneId: network.outputs.dnsZoneIds.blob
  }
}

module peSearchApp './modules/private-endpoint.bicep' = {
  name: 'pe-search-app'
  scope: rg
  params: {
    name: 'pe-search-app-${resourceToken}'
    location: location
    tags: tags
    subnetId: network.outputs.snetAppPeId
    privateLinkServiceId: search.outputs.id
    groupId: 'searchService'
    privateDnsZoneId: network.outputs.dnsZoneIds.search
  }
}

module peOpenaiApp './modules/private-endpoint.bicep' = {
  name: 'pe-openai-app'
  scope: rg
  params: {
    name: 'pe-openai-app-${resourceToken}'
    location: location
    tags: tags
    subnetId: network.outputs.snetAppPeId
    privateLinkServiceId: openai.outputs.id
    groupId: 'account'
    privateDnsZoneId: network.outputs.dnsZoneIds.openai
  }
}

module peKvApp './modules/private-endpoint.bicep' = {
  name: 'pe-kv-app'
  scope: rg
  params: {
    name: 'pe-kv-app-${resourceToken}'
    location: location
    tags: tags
    subnetId: network.outputs.snetAppPeId
    privateLinkServiceId: agentStores.outputs.keyVaultId
    groupId: 'vault'
    privateDnsZoneId: network.outputs.dnsZoneIds.keyVault
  }
}

// ═══════════════════════════════════════════════════════════════════════
// PRIVATE ENDPOINTS — Agent-Dedicated Services (Foundry PE subnet)
// ═══════════════════════════════════════════════════════════════════════

module peCosmosAgent './modules/private-endpoint.bicep' = {
  name: 'pe-cosmos-agent'
  scope: rg
  params: {
    name: 'pe-cosmos-agent-${resourceToken}'
    location: location
    tags: tags
    subnetId: network.outputs.snetFoundryPeId
    privateLinkServiceId: agentStores.outputs.cosmosId
    groupId: 'Sql'
    privateDnsZoneId: network.outputs.dnsZoneIds.cosmos
  }
}

module peStorageAgent './modules/private-endpoint.bicep' = {
  name: 'pe-storage-agent'
  scope: rg
  params: {
    name: 'pe-storage-agent-${resourceToken}'
    location: location
    tags: tags
    subnetId: network.outputs.snetFoundryPeId
    privateLinkServiceId: agentStores.outputs.storageId
    groupId: 'blob'
    privateDnsZoneId: network.outputs.dnsZoneIds.blob
  }
}

module peSearchAgent './modules/private-endpoint.bicep' = {
  name: 'pe-search-agent'
  scope: rg
  params: {
    name: 'pe-search-agent-${resourceToken}'
    location: location
    tags: tags
    subnetId: network.outputs.snetFoundryPeId
    privateLinkServiceId: agentStores.outputs.searchId
    groupId: 'searchService'
    privateDnsZoneId: network.outputs.dnsZoneIds.search
  }
}

module peKvAgent './modules/private-endpoint.bicep' = {
  name: 'pe-kv-agent'
  scope: rg
  params: {
    name: 'pe-kv-agent-${resourceToken}'
    location: location
    tags: tags
    subnetId: network.outputs.snetFoundryPeId
    privateLinkServiceId: agentStores.outputs.keyVaultId
    groupId: 'vault'
    privateDnsZoneId: network.outputs.dnsZoneIds.keyVault
  }
}

// ═══════════════════════════════════════════════════════════════════════
// OUTPUTS
// ═══════════════════════════════════════════════════════════════════════

output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_OPENAI_ENDPOINT string = openai.outputs.endpoint
output AZURE_CONTENT_SAFETY_ENDPOINT string = contentSafety.outputs.endpoint
output AZURE_SEARCH_ENDPOINT string = search.outputs.endpoint
output AZURE_COSMOS_ENDPOINT string = cosmos.outputs.endpoint
output AZURE_STORAGE_ENDPOINT string = storage.outputs.endpoint
output AZURE_FOUNDRY_ENDPOINT string = foundry.outputs.projectEndpoint
output AZURE_FOUNDRY_PROJECT string = foundry.outputs.projectName
output BACKEND_URL string = containerApps.outputs.apiUrl
output FRONTEND_URL string = staticWebApp.outputs.url
output FRONT_DOOR_URL string = frontDoor.outputs.frontDoorFqdn
output ACR_LOGIN_SERVER string = acr.outputs.loginServer
output APP_IDENTITY_CLIENT_ID string = identity.outputs.appIdentityClientId
