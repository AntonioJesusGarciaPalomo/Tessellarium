// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Azure Front Door Premium + WAF
// ──────────────────────────────────────────────────────────────────────

@description('Name prefix for Front Door resources')
param name string
param location string = 'global'
param tags object = {}

@description('Backend Container App FQDN (e.g. ca-tess-api.niceground-abc.swedencentral.azurecontainerapps.io)')
param backendFqdn string

// ─── WAF Policy ─────────────────────────────────────────────────────

resource wafPolicy 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2024-02-01' = {
  name: 'waf${replace(name, '-', '')}'
  location: location
  tags: tags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
  properties: {
    policySettings: {
      mode: 'Prevention'
      requestBodyCheck: 'Enabled'
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'Microsoft_DefaultRuleSet'
          ruleSetVersion: '2.1'
        }
        {
          ruleSetType: 'Microsoft_BotManagerRuleSet'
          ruleSetVersion: '1.1'
        }
      ]
    }
  }
}

// ─── Front Door Profile ─────────────────────────────────────────────

resource frontDoor 'Microsoft.Cdn/profiles@2024-02-01' = {
  name: 'afd-${name}'
  location: location
  tags: tags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
}

// ─── Backend API endpoint ───────────────────────────────────────────

resource apiEndpoint 'Microsoft.Cdn/profiles/afdEndpoints@2024-02-01' = {
  parent: frontDoor
  name: 'api'
  location: location
  properties: {
    enabledState: 'Enabled'
  }
}

resource apiOriginGroup 'Microsoft.Cdn/profiles/originGroups@2024-02-01' = {
  parent: frontDoor
  name: 'api-origin-group'
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
    }
    healthProbeSettings: {
      probePath: '/health'
      probeRequestType: 'GET'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 30
    }
  }
}

resource apiOrigin 'Microsoft.Cdn/profiles/originGroups/origins@2024-02-01' = {
  parent: apiOriginGroup
  name: 'api-backend'
  properties: {
    hostName: backendFqdn
    httpPort: 80
    httpsPort: 443
    originHostHeader: backendFqdn
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
  }
}

resource apiRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2024-02-01' = {
  parent: apiEndpoint
  name: 'api-route'
  properties: {
    originGroup: {
      id: apiOriginGroup.id
    }
    supportedProtocols: ['Https']
    patternsToMatch: ['/api/*', '/health']
    forwardingProtocol: 'HttpsOnly'
    linkToDefaultDomain: 'Enabled'
    httpsRedirect: 'Enabled'
  }
  dependsOn: [apiOrigin]
}

// ─── Security policy ────────────────────────────────────────────────

resource securityPolicy 'Microsoft.Cdn/profiles/securityPolicies@2024-02-01' = {
  parent: frontDoor
  name: 'waf-policy'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      wafPolicy: {
        id: wafPolicy.id
      }
      associations: [
        {
          domains: [
            { id: apiEndpoint.id }
          ]
          patternsToMatch: ['/*']
        }
      ]
    }
  }
}

// ─── Outputs ────────────────────────────────────────────────────────

output frontDoorId string = frontDoor.id
output apiEndpointHostname string = apiEndpoint.properties.hostName
output frontDoorFqdn string = 'https://${apiEndpoint.properties.hostName}'
