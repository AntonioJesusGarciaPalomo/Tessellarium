// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Container Apps (Production)
// Workload profiles environment, 3 apps, managed identity auth
// ──────────────────────────────────────────────────────────────────────

@description('Name of the Container Apps Environment')
param name string
param location string
param tags object = {}

@description('Subnet ID for the Container Apps Environment (delegated)')
param subnetId string

@description('User-assigned managed identity resource ID')
param appIdentityId string

@description('ACR login server (e.g. crtess.azurecr.io)')
param acrLoginServer string

// ─── Service endpoints (managed identity — no keys) ─────────────────
param openaiEndpoint string
param contentSafetyEndpoint string
param searchEndpoint string
param cosmosEndpoint string
param storageEndpoint string
param foundryEndpoint string = ''
param foundryProject string = ''

@secure()
param leanMcpToken string = 'tessellarium-lean-token-change-me'

// ─── Log Analytics ──────────────────────────────────────────────────

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${name}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ─── Container Registry ─────────────────────────────────────────────

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: replace('cr${name}', '-', '')
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

// ─── Container Apps Environment (Workload Profiles) ─────────────────

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
    vnetConfiguration: {
      infrastructureSubnetId: subnetId
      internal: false
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
      {
        name: 'Dedicated-D4'
        workloadProfileType: 'D4'
        minimumCount: 0
        maximumCount: 3
      }
    ]
  }
}

// ─── tess-api (Backend API) ─────────────────────────────────────────

resource tessApi 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-tess-api'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${appIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: env.id
    workloadProfileName: 'Consumption'
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
      registries: [
        {
          server: acrLoginServer
          identity: appIdentityId
        }
      ]
      secrets: [
        { name: 'lean-mcp-token', value: leanMcpToken }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${acrLoginServer}/tessellarium-backend:latest'
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: [
            { name: 'AZURE_OPENAI_ENDPOINT', value: openaiEndpoint }
            { name: 'CONTENT_SAFETY_ENDPOINT', value: contentSafetyEndpoint }
            { name: 'SEARCH_ENDPOINT', value: searchEndpoint }
            { name: 'COSMOS_ENDPOINT', value: cosmosEndpoint }
            { name: 'STORAGE_ENDPOINT', value: storageEndpoint }
            { name: 'AZURE_FOUNDRY_ENDPOINT', value: foundryEndpoint }
            { name: 'AZURE_FOUNDRY_PROJECT', value: foundryProject }
            { name: 'AZURE_CLIENT_ID', value: '' } // set via identity
            { name: 'LEAN_SERVICE_URL', value: 'https://ca-tess-lean.internal.${env.properties.defaultDomain}:8001' }
            { name: 'LEAN_MCP_TOKEN', secretRef: 'lean-mcp-token' }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 3 }
    }
  }
}

// ─── tess-worker (Background tasks: indexing, verification dispatch) ─

resource tessWorker 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-tess-worker'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${appIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      registries: [
        {
          server: acrLoginServer
          identity: appIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: '${acrLoginServer}/tessellarium-backend:latest'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'AZURE_OPENAI_ENDPOINT', value: openaiEndpoint }
            { name: 'SEARCH_ENDPOINT', value: searchEndpoint }
            { name: 'COSMOS_ENDPOINT', value: cosmosEndpoint }
            { name: 'STORAGE_ENDPOINT', value: storageEndpoint }
            { name: 'WORKER_MODE', value: 'true' }
          ]
          command: ['python', '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000']
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 2 }
    }
  }
}

// ─── tess-lean-verify (Lean 4 verification service) ─────────────────

resource tessLean 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-tess-lean'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: env.id
    workloadProfileName: 'Dedicated-D4'
    configuration: {
      ingress: {
        external: true
        targetPort: 8001
        transport: 'auto'
      }
      registries: [
        {
          server: acrLoginServer
          identity: appIdentityId
        }
      ]
      secrets: [
        { name: 'lean-mcp-token', value: leanMcpToken }
      ]
    }
    template: {
      containers: [
        {
          name: 'lean'
          image: '${acrLoginServer}/tessellarium-lean:latest'
          resources: { cpu: json('2.0'), memory: '4Gi' }
          env: [
            { name: 'LEAN_PROJECT_PATH', value: '/workspace' }
            { name: 'LEAN_LSP_MCP_TOKEN', secretRef: 'lean-mcp-token' }
            { name: 'LEAN_REPL', value: 'true' }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 1 }
    }
  }
}

// ─── Outputs ────────────────────────────────────────────────────────

output apiUrl string = 'https://${tessApi.properties.configuration.ingress.fqdn}'
output apiFqdn string = tessApi.properties.configuration.ingress.fqdn
output leanUrl string = 'https://${tessLean.properties.configuration.ingress.fqdn}'
output registryLoginServer string = containerRegistry.properties.loginServer
output registryName string = containerRegistry.name
output registryId string = containerRegistry.id
output environmentDefaultDomain string = env.properties.defaultDomain
