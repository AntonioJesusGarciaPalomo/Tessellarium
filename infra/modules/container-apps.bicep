@description('Name of the Container Apps Environment')
param name string
param location string
param tags object = {}
param backendImageName string

@secure()
param openaiEndpoint string
@secure()
param openaiApiKey string
@secure()
param contentSafetyEndpoint string
@secure()
param contentSafetyApiKey string
@secure()
param searchEndpoint string
@secure()
param searchApiKey string
@secure()
param cosmosEndpoint string
@secure()
param cosmosKey string

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${name}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: replace('cr${name}', '-', '')
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: true }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource backend 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-tessellarium-backend'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
        }
      }
      secrets: [
        { name: 'openai-key', value: openaiApiKey }
        { name: 'safety-key', value: contentSafetyApiKey }
        { name: 'search-key', value: searchApiKey }
        { name: 'cosmos-key', value: cosmosKey }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: backendImageName
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: [
            { name: 'AZURE_OPENAI_ENDPOINT', value: openaiEndpoint }
            { name: 'AZURE_OPENAI_API_KEY', secretRef: 'openai-key' }
            { name: 'CONTENT_SAFETY_ENDPOINT', value: contentSafetyEndpoint }
            { name: 'CONTENT_SAFETY_API_KEY', secretRef: 'safety-key' }
            { name: 'SEARCH_ENDPOINT', value: searchEndpoint }
            { name: 'SEARCH_API_KEY', secretRef: 'search-key' }
            { name: 'COSMOS_ENDPOINT', value: cosmosEndpoint }
            { name: 'COSMOS_KEY', secretRef: 'cosmos-key' }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 3 }
    }
  }
}

output backendUrl string = 'https://${backend.properties.configuration.ingress.fqdn}'
output registryLoginServer string = containerRegistry.properties.loginServer
output registryName string = containerRegistry.name
