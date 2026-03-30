// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Azure AI Search (Production)
// Semantic search enabled, private endpoint ready
// ──────────────────────────────────────────────────────────────────────

@description('Name of the Search resource')
param name string
param location string
param tags object = {}

@description('SKU: basic for dev, standard for production with zone redundancy')
param skuName string = 'basic'

@description('Number of replicas (2+ for HA)')
param replicaCount int = 1

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: { name: skuName }
  properties: {
    replicaCount: replicaCount
    partitionCount: 1
    hostingMode: 'default'
    semanticSearch: 'standard'
    publicNetworkAccess: 'disabled'
    networkRuleSet: {
      bypass: 'AzureServices'
    }
  }
}

output id string = search.id
output endpoint string = 'https://${search.name}.search.windows.net'
output name string = search.name
