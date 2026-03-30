// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Reusable Private Endpoint Module
// ──────────────────────────────────────────────────────────────────────

@description('Name of the private endpoint')
param name string
param location string
param tags object = {}

@description('Subnet ID to place the private endpoint in')
param subnetId string

@description('Resource ID of the target service')
param privateLinkServiceId string

@description('Group ID for the private link (e.g. Sql, blob, searchService, vault, account)')
param groupId string

@description('Private DNS zone resource ID for auto-registration')
param privateDnsZoneId string

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2024-01-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [
      {
        name: '${name}-conn'
        properties: {
          privateLinkServiceId: privateLinkServiceId
          groupIds: [groupId]
        }
      }
    ]
  }
}

resource dnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'config'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

output id string = privateEndpoint.id
