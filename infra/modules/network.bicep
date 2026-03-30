// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Virtual Network & Private DNS
// ──────────────────────────────────────────────────────────────────────

@description('Name prefix for network resources')
param name string
param location string
param tags object = {}

var vnetName = 'vnet-${name}'
var vnetAddressSpace = '10.0.0.0/16'

// ─── Subnets ────────────────────────────────────────────────────────

var subnets = [
  {
    name: 'snet-app-aca'
    addressPrefix: '10.0.1.0/24'
    delegations: [
      {
        name: 'aca-delegation'
        properties: {
          serviceName: 'Microsoft.App/environments'
        }
      }
    ]
  }
  {
    name: 'snet-app-pe'
    addressPrefix: '10.0.2.0/24'
    delegations: []
  }
  {
    name: 'snet-foundry-agents'
    addressPrefix: '10.0.3.0/24'
    delegations: []
  }
  {
    name: 'snet-foundry-pe'
    addressPrefix: '10.0.4.0/24'
    delegations: []
  }
]

// ─── VNet ───────────────────────────────────────────────────────────

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [vnetAddressSpace]
    }
    subnets: [
      for subnet in subnets: {
        name: subnet.name
        properties: {
          addressPrefix: subnet.addressPrefix
          delegations: subnet.delegations
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

// ─── Private DNS Zones ──────────────────────────────────────────────

var privateDnsZones = [
  'privatelink.documents.azure.com'           // Cosmos DB
  'privatelink.blob.core.windows.net'         // Blob Storage
  'privatelink.search.windows.net'            // AI Search
  'privatelink.vaultcore.azure.net'           // Key Vault
  'privatelink.openai.azure.com'              // Azure OpenAI
  'privatelink.cognitiveservices.azure.com'   // Content Safety / CU
]

resource dnsZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [
  for zone in privateDnsZones: {
    name: zone
    location: 'global'
    tags: tags
  }
]

resource dnsZoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [
  for (zone, i) in privateDnsZones: {
    parent: dnsZones[i]
    name: '${vnetName}-link'
    location: 'global'
    properties: {
      virtualNetwork: {
        id: vnet.id
      }
      registrationEnabled: false
    }
  }
]

// ─── Subnet References (by name, not index) ────────────────────────

resource snetAppAca 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' existing = {
  parent: vnet
  name: 'snet-app-aca'
}

resource snetAppPe 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' existing = {
  parent: vnet
  name: 'snet-app-pe'
}

resource snetFoundryAgents 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' existing = {
  parent: vnet
  name: 'snet-foundry-agents'
}

resource snetFoundryPe 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' existing = {
  parent: vnet
  name: 'snet-foundry-pe'
}

// ─── Outputs ────────────────────────────────────────────────────────

output vnetId string = vnet.id
output vnetName string = vnet.name
output snetAppAcaId string = snetAppAca.id
output snetAppPeId string = snetAppPe.id
output snetFoundryAgentsId string = snetFoundryAgents.id
output snetFoundryPeId string = snetFoundryPe.id

output dnsZoneIds object = {
  cosmos: dnsZones[0].id
  blob: dnsZones[1].id
  search: dnsZones[2].id
  keyVault: dnsZones[3].id
  openai: dnsZones[4].id
  cognitiveServices: dnsZones[5].id
}
