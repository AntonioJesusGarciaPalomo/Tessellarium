// ──────────────────────────────────────────────────────────────────────
// Tessellarium — Managed Identities & Role Assignments
// ──────────────────────────────────────────────────────────────────────

@description('Name prefix for identity resources')
param name string
param location string
param tags object = {}

// Resource IDs to grant access to
param acrId string = ''
param cosmosAppAccountId string = ''
param cosmosAgentAccountId string = ''
param cosmosAppAccountName string = ''
param cosmosAgentAccountName string = ''
param storageAppAccountId string = ''
param storageAgentAccountId string = ''
param openaiAccountId string = ''
param searchAppId string = ''
param searchAgentId string = ''
param keyVaultAppId string = ''
param keyVaultAgentId string = ''

// ─── User-Assigned Managed Identities ───────────────────────────────

resource appIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${name}-app'
  location: location
  tags: tags
}

resource foundryIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${name}-foundry'
  location: location
  tags: tags
}

// ─── Built-in Role Definition IDs ───────────────────────────────────

// Cosmos DB: Cosmos DB Built-in Data Contributor
var cosmosDataContributor = '00000000-0000-0000-0000-000000000002'

// Storage: Storage Blob Data Contributor
var storageBlobContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

// Cognitive Services: Cognitive Services OpenAI User
var cognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

// Search: Search Index Data Contributor
var searchIndexDataContributor = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'

// Key Vault: Key Vault Secrets User
var keyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'

// ACR: AcrPull
var acrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

// ─── ACR Pull for Container Apps ────────────────────────────────────

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (acrId != '') {
  name: guid(acrId, appIdentity.id, acrPull)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull)
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─── OpenAI access ──────────────────────────────────────────────────

resource openaiAppAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (openaiAccountId != '') {
  name: guid(openaiAccountId, appIdentity.id, cognitiveServicesOpenAIUser)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUser)
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource openaiFoundryAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (openaiAccountId != '') {
  name: guid(openaiAccountId, foundryIdentity.id, cognitiveServicesOpenAIUser)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUser)
    principalId: foundryIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Storage access ─────────────────────────────────────────────────

resource storageAppAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (storageAppAccountId != '') {
  name: guid(storageAppAccountId, appIdentity.id, storageBlobContributor)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobContributor)
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageAgentAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (storageAgentAccountId != '') {
  name: guid(storageAgentAccountId, foundryIdentity.id, storageBlobContributor)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobContributor)
    principalId: foundryIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Key Vault access ───────────────────────────────────────────────

resource kvAppAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (keyVaultAppId != '') {
  name: guid(keyVaultAppId, appIdentity.id, keyVaultSecretsUser)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUser)
    principalId: appIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource kvAgentAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (keyVaultAgentId != '') {
  name: guid(keyVaultAgentId, foundryIdentity.id, keyVaultSecretsUser)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUser)
    principalId: foundryIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Cosmos DB Data-Plane RBAC ───────────────────────────────────────
// Cosmos uses its own sqlRoleAssignments, not Microsoft.Authorization.
// Built-in role: 00000000-0000-0000-0000-000000000002 = Cosmos DB Built-in Data Contributor

resource cosmosAppAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = if (cosmosAppAccountName != '') {
  name: cosmosAppAccountName
}

resource cosmosAppRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (cosmosAppAccountName != '') {
  parent: cosmosAppAccount
  name: guid(cosmosAppAccountId, appIdentity.id, cosmosDataContributor)
  properties: {
    roleDefinitionId: '${cosmosAppAccountId}/sqlRoleDefinitions/${cosmosDataContributor}'
    principalId: appIdentity.properties.principalId
    scope: cosmosAppAccountId
  }
}

resource cosmosAgentAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = if (cosmosAgentAccountName != '') {
  name: cosmosAgentAccountName
}

resource cosmosAgentRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (cosmosAgentAccountName != '') {
  parent: cosmosAgentAccount
  name: guid(cosmosAgentAccountId, foundryIdentity.id, cosmosDataContributor)
  properties: {
    roleDefinitionId: '${cosmosAgentAccountId}/sqlRoleDefinitions/${cosmosDataContributor}'
    principalId: foundryIdentity.properties.principalId
    scope: cosmosAgentAccountId
  }
}

// ─── Outputs ────────────────────────────────────────────────────────

output appIdentityId string = appIdentity.id
output appIdentityPrincipalId string = appIdentity.properties.principalId
output appIdentityClientId string = appIdentity.properties.clientId
output foundryIdentityId string = foundryIdentity.id
output foundryIdentityPrincipalId string = foundryIdentity.properties.principalId
output foundryIdentityClientId string = foundryIdentity.properties.clientId
