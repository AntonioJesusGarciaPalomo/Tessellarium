// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Microsoft Foundry Resource & Project
//
// NOTE: As of March 2026, Foundry projects are provisioned via the
// Microsoft.MachineLearningServices/workspaces resource type with
// kind='Project'. Agent definitions, tool connections, and Foundry IQ
// knowledge bases are configured post-deployment via SDK or portal.
// ──────────────────────────────────────────────────────────────────────

@description('Name prefix for Foundry resources')
param name string
param location string
param tags object = {}

@description('User-assigned managed identity for the Foundry project')
param identityId string

@description('Azure OpenAI account resource ID for model connection')
param openaiAccountId string

@description('AI Search resource ID for Foundry IQ')
param searchAccountId string

@description('Storage account resource ID for agent file storage')
param storageAccountId string

@description('Cosmos DB account resource ID for BYO thread storage')
param cosmosAccountId string

@description('Key Vault resource ID for agent secrets')
param keyVaultId string

// ─── Foundry Hub (AI Hub workspace) ─────────────────────────────────

resource hub 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: 'hub-${name}'
  location: location
  tags: tags
  kind: 'Hub'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    friendlyName: 'Tessellarium AI Hub'
    description: 'Hub for Tessellarium Foundry project and agents'
    storageAccount: storageAccountId
    keyVault: keyVaultId
    primaryUserAssignedIdentity: identityId
    publicNetworkAccess: 'Enabled'
  }
}

// ─── Foundry Project ────────────────────────────────────────────────

resource project 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: 'proj-${name}'
  location: location
  tags: tags
  kind: 'Project'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    friendlyName: 'Tessellarium'
    description: 'Decisive Experiment Compiler — Foundry project for agent orchestration'
    hubResourceId: hub.id
    primaryUserAssignedIdentity: identityId
    publicNetworkAccess: 'Enabled'
  }
}

// ─── Connections (OpenAI, Search, Cosmos) ────────────────────────────
// NOTE: Connections to OpenAI, AI Search, Cosmos DB, and the Lean MCP
// endpoint are configured post-deployment via:
//   az ml connection create --file connection.yaml
// or via the azure-ai-projects SDK. Bicep support for workspace
// connections varies by resource type and API version.

// ─── Outputs ────────────────────────────────────────────────────────

output hubId string = hub.id
output projectId string = project.id
output projectName string = project.name
output projectEndpoint string = 'https://${location}.api.azureml.ms'
