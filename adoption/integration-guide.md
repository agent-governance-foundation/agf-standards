# Integration Guide: Migrating from Existing IAM

**Version:** 1.0.0 (Draft)  
**Status:** Working Draft

This guide describes a planned integration path, not a description of any particular deployment. Treat it as an illustrative design for bridging an existing IAM system to AGF, useful for a from-scratch conformant implementation.

## 1. Overview

This guide helps enterprises integrate Agent Governance Foundation (AGF) with existing IAM systems: Okta, Azure AD, Active Directory, LDAP, and custom identity providers.

## 2. Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│  Existing   │────▶│     Bridge      │────▶│     AGF     │
│    IAM      │     │    Service      │     │  Services   │
│ (Okta,      │     │                 │     │             │
│  Azure AD)  │     └─────────────────┘     └─────────────┘
└─────────────┘
```

The bridge service translates between existing identities and AGF DIDs.

## 3. Identity Mapping

### 3.1 User to DID Mapping

| Source | Target | Example |
|--------|--------|---------|
| Okta `user.id` | `did:agf:{okta-org}:user:{user-id}` | `did:agf:acme:user:abc123` |
| Azure AD `objectId` | `did:agf:{tenant}:user:{object-id}` | `did:agf:acme:user:def456` |
| LDAP `dn` | `did:agf:{domain}:user:{hash(dn)}` | `did:agf:acme:user:ghi789` |

### 3.2 Group to Role Mapping

Existing IAM groups become AGF roles:

```yaml
# bridge-config.yaml
mappings:
  - source:
      provider: "okta"
      group: "Finance-Managers"
    target:
      role: "approve:payment"
      max_amount: 1000000
  - source:
      provider: "azure-ad"
      group: "devops-team"
    target:
      role: "execute:deployment"
      environment: "production"
```

## 4. Bridge Service API

### 4.1 User Authentication

Agent requests a DID for a human user:

```bash
POST /v1/bridge/authenticate
{
  "id_token": "eyJ0eXAi...",
  "provider": "okta"
}
```

Response:

```json
{
  "did": "did:agf:acme:user:alice-123",
  "delegation_token": "eyJ0eXAi...",
  "expires_in": 3600
}
```

### 4.2 Group Membership Sync

Periodic sync:

```bash
POST /v1/bridge/sync
{
  "provider": "azure-ad",
  "since": "2026-06-01T00:00:00Z"
}
```

## 5. Deployment Options

### Option A: Sidecar (Recommended)

Run bridge service alongside existing IAM proxies:

```
User → Okta → Bridge → AGF PDP → Resource
```

### Option B: Direct Integration

Call AGF APIs directly from existing IAM using webhooks.

### Option C: Gradual Migration

1. Start with read-only sync (no delegation issuance)
2. Enable for non-critical agents
3. Gradually migrate critical workflows
4. Decommission old IAM integrations

## 6. Configuration Examples

### 6.1 Okta Integration

```yaml
okta:
  domain: "dev-123456.okta.com"
  api_token: "${OKTA_API_TOKEN}"
  sync_interval_seconds: 300
  group_mappings:
    - okta_group: "Everyone"
      agf_role: "read:calendar"
    - okta_group: "Finance"
      agf_role: "approve:payment"
```

### 6.2 Azure AD Integration

```yaml
azure_ad:
  tenant_id: "${AZURE_TENANT_ID}"
  client_id: "${AZURE_CLIENT_ID}"
  client_secret: "${AZURE_CLIENT_SECRET}"
  sync_interval_seconds: 600
```

## 7. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
