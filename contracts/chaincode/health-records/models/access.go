package models

import (
    "time"
)

// AccessGrant represents an access grant to a resource
type AccessGrant struct {
    GrantID      string    `json:"grantId"`
    ResourceID   string    `json:"resourceId"`
    GrantorID    string    `json:"grantorId"`
    GranteeID    string    `json:"granteeId"`
    Permissions  []string  `json:"permissions"`
    GrantedAt    time.Time `json:"grantedAt"`
    ExpiresAt    time.Time `json:"expiresAt"`
    Conditions   []string  `json:"conditions"`
    Status       string    `json:"status"`
    ObjectType   string    `json:"objectType"`
}

// AccessPolicy represents an access control policy
type AccessPolicy struct {
    PolicyID     string       `json:"policyId"`
    PolicyName   string       `json:"policyName"`
    ResourceType string       `json:"resourceType"`
    Rules        []AccessRule `json:"rules"`
    CreatedBy    string       `json:"createdBy"`
    CreatedAt    time.Time    `json:"createdAt"`
    Active       bool         `json:"active"`
    ObjectType   string       `json:"objectType"`
}

// AccessRule represents a single rule in an access policy
type AccessRule struct {
    RuleID     string   `json:"ruleId"`
    Role       string   `json:"role"`
    Actions    []string `json:"actions"`
    Conditions []string `json:"conditions"`
    Duration   string   `json:"duration,omitempty"`
}

// Access grant status constants
const (
    AccessStatusActive   = "active"
    AccessStatusRevoked  = "revoked"
    AccessStatusExpired  = "expired"
)

// Permission constants
const (
    PermissionRead      = "read"
    PermissionWrite     = "write"
    PermissionDelete    = "delete"
    PermissionGrant     = "grant"
    PermissionRevoke    = "revoke"
    PermissionVerify    = "verify"
    PermissionReadOwn   = "read:own"
    PermissionWriteOwn  = "write:own"
    PermissionGrantOwn  = "grant:own"
    PermissionRevokeOwn = "revoke:own"
    PermissionDelegate  = "delegate"
    PermissionAdmin     = "admin"
)

// Role constants
const (
    RolePatient       = "PATIENT"
    RoleProvider      = "PROVIDER"
    RoleVerifier      = "VERIFIER"
    RoleAdministrator = "ADMINISTRATOR"
    RoleEmergency     = "EMERGENCY"
)

// NewAccessGrant creates a new access grant
func NewAccessGrant(resourceID, grantorID, granteeID string, permissions []string) *AccessGrant {
    return &AccessGrant{
        ResourceID:  resourceID,
        GrantorID:   grantorID,
        GranteeID:   granteeID,
        Permissions: permissions,
        GrantedAt:   time.Now(),
        ExpiresAt:   time.Now().Add(30 * 24 * time.Hour), // 30 days default
        Status:      AccessStatusActive,
        ObjectType:  "accessGrant",
        Conditions:  []string{},
    }
}

// NewAccessPolicy creates a new access policy
func NewAccessPolicy(policyID, policyName, resourceType, createdBy string) *AccessPolicy {
    return &AccessPolicy{
        PolicyID:     policyID,
        PolicyName:   policyName,
        ResourceType: resourceType,
        Rules:        []AccessRule{},
        CreatedBy:    createdBy,
        CreatedAt:    time.Now(),
        Active:       true,
        ObjectType:   "accessPolicy",
    }
}

// IsExpired checks if the access grant has expired
func (ag *AccessGrant) IsExpired() bool {
    return time.Now().After(ag.ExpiresAt)
}

// IsActive checks if the access grant is active and not expired
func (ag *AccessGrant) IsActive() bool {
    return ag.Status == AccessStatusActive && !ag.IsExpired()
}

// HasPermission checks if the grant includes a specific permission
func (ag *AccessGrant) HasPermission(permission string) bool {
    for _, p := range ag.Permissions {
        if p == permission {
            return true
        }
    }
    return false
}

// AddRule adds a new rule to the access policy
func (ap *AccessPolicy) AddRule(rule AccessRule) {
    ap.Rules = append(ap.Rules, rule)
}

// GetRulesForRole returns all rules that apply to a specific role
func (ap *AccessPolicy) GetRulesForRole(role string) []AccessRule {
    var rules []AccessRule
    for _, rule := range ap.Rules {
        if rule.Role == role {
            rules = append(rules, rule)
        }
    }
    return rules
}
