@description('Name of the Static Web App')
param name string
param location string
param tags object = {}

resource staticWebApp 'Microsoft.Web/staticSites@2023-12-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: 'Free', tier: 'Free' }
  properties: {
    buildProperties: {
      appLocation: '/frontend'
      outputLocation: 'build'
    }
  }
}

output url string = 'https://${staticWebApp.properties.defaultHostname}'
output name string = staticWebApp.name
