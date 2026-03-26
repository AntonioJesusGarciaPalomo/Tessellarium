// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Azure Infrastructure
// Decisive Experiment Compiler
// ──────────────────────────────────────────────────────────────────────

targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (e.g., dev, prod)')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Name of the Azure OpenAI model deployment for GPT-4o')
param gpt4oDeploymentName string = 'gpt-4o'

@description('Name of the Azure OpenAI model deployment for GPT-4o-mini')
param gpt4oMiniDeploymentName string = 'gpt-4o-mini'

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName, project: 'tessellarium' }

resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: '${abbrs.resourceGroup}tessellarium-${environmentName}'
  location: location
  tags: tags
}

module openai './modules/openai.bicep' = {
  name: 'openai'
  scope: rg
  params: {
    name: '${abbrs.cognitiveServicesAccount}${resourceToken}'
    location: location
    tags: tags
    gpt4oDeploymentName: gpt4oDeploymentName
    gpt4oMiniDeploymentName: gpt4oMiniDeploymentName
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

module containerApps './modules/container-apps.bicep' = {
  name: 'container-apps'
  scope: rg
  params: {
    name: '${abbrs.containerAppsEnvironment}${resourceToken}'
    location: location
    tags: tags
    backendImageName: 'tessellarium-backend:latest'
    openaiEndpoint: openai.outputs.endpoint
    openaiApiKey: openai.outputs.apiKey
    contentSafetyEndpoint: contentSafety.outputs.endpoint
    contentSafetyApiKey: contentSafety.outputs.apiKey
    searchEndpoint: search.outputs.endpoint
    searchApiKey: search.outputs.apiKey
    cosmosEndpoint: cosmos.outputs.endpoint
    cosmosKey: cosmos.outputs.key
  }
}

module staticWebApp './modules/static-web-app.bicep' = {
  name: 'static-web-app'
  scope: rg
  params: {
    name: '${abbrs.staticWebApp}${resourceToken}'
    location: location
    tags: tags
  }
}

output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_OPENAI_ENDPOINT string = openai.outputs.endpoint
output AZURE_CONTENT_SAFETY_ENDPOINT string = contentSafety.outputs.endpoint
output AZURE_SEARCH_ENDPOINT string = search.outputs.endpoint
output AZURE_COSMOS_ENDPOINT string = cosmos.outputs.endpoint
output BACKEND_URL string = containerApps.outputs.backendUrl
output FRONTEND_URL string = staticWebApp.outputs.url
