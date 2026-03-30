// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Azure Container Registry
// ──────────────────────────────────────────────────────────────────────

@description('Name of the Container Registry')
param name string
param location string
param tags object = {}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: replace(name, '-', '')
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

output id string = containerRegistry.id
output loginServer string = containerRegistry.properties.loginServer
output name string = containerRegistry.name
