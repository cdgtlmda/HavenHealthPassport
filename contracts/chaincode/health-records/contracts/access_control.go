package contracts

import (
    "encoding/json"
    "fmt"
    "strings"
    "time"

    "github.com/haven-health-passport/chaincode/health-records/models"
    "github.com/haven-health-passport/chaincode/health-records/utils"
    "github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// AccessControlContract provides functions for managing access control
type AccessControlContract struct {
    contractapi.Contract
}

// GrantAccess grants access to a resource
func (acc *AccessControlContract) GrantAccess(
    ctx contractapi.TransactionContextInterface,
    resourceID string,
    granteeID string,
    permissions string, // JSON array of permissions
    expirationHours int,
    conditions string, // JSON array of conditions
) error {
    // Get grantor identity
    grantorID, err := ctx.GetClientIdentity().GetID()
    if err != nil {
        return fmt.Errorf("failed to get grantor identity: %v", err)
    }

    // Parse permissions
    var permissionList []string
    err = json.Unmarshal([]byte(permissions), &permissionList)
    if err != nil {
        return fmt.Errorf("failed to parse permissions: %v", err)
    }

    // Parse conditions
    var conditionList []string
    if conditions != "" {
        err = json.Unmarshal([]byte(conditions), &conditionList)
        if err != nil {
            return fmt.Errorf("failed to parse conditions: %v", err)
        }
    }

    // Generate grant ID
    grantID, err := utils.GenerateRecordID()
    if err != nil {
        return fmt.Errorf("failed to generate grant ID: %v", err)
    }

    // Create access grant with time-based access
    grant := models.NewAccessGrant(resourceID, grantorID, granteeID, permissionList)
    grant.GrantID = grantID
    grant.Conditions = conditionList

    // Set expiration based on hours (0 means 30 days default)
    if expirationHours > 0 {
        grant.ExpiresAt = time.Now().Add(time.Duration(expirationHours) * time.Hour)
    }

    // Add granular permissions validation
    err = acc.validateGranularPermissions(ctx, grantorID, resourceID, permissionList)
    if err != nil {
        return fmt.Errorf("permission validation failed: %v", err)
    }

    // Validate grant
    err = utils.ValidateAccessGrant(grant)
    if err != nil {
        return fmt.Errorf("grant validation failed: %v", err)
    }

    // Check for delegation support
    if acc.isDelegatedGrant(permissionList) {
        // Verify grantor has delegation rights
        canDelegate, err := acc.checkDelegationRights(ctx, grantorID, resourceID)
        if err != nil || !canDelegate {
            return fmt.Errorf("grantor does not have delegation rights")
        }
    }

    // Store grant
    grantKey := utils.CreateAccessKey(resourceID, granteeID, grantID)
    grantJSON, err := json.Marshal(grant)
    if err != nil {
        return fmt.Errorf("failed to marshal grant: %v", err)
    }

    err = ctx.GetStub().PutState(grantKey, grantJSON)
    if err != nil {
        return fmt.Errorf("failed to store grant: %v", err)
    }

    // Create user grant index
    userGrantKey, err := ctx.GetStub().CreateCompositeKey(
        utils.PrefixUserGrants,
        []string{granteeID, grantID},
    )
    if err != nil {
        return fmt.Errorf("failed to create user grant index: %v", err)
    }
    ctx.GetStub().PutState(userGrantKey, []byte{0x00})

    // Store in access history
    acc.recordAccessHistory(ctx, "GRANT_CREATED", grantID, grantorID, resourceID, granteeID)

    // Clear any cached permissions for this user/resource
    acc.clearPermissionCache(ctx, granteeID, resourceID)

    // Emit event
    event := map[string]interface{}{
        "eventType":   "ACCESS_GRANTED",
        "grantId":     grantID,
        "resourceId":  resourceID,
        "grantorId":   grantorID,
        "granteeId":   granteeID,
        "permissions": permissionList,
        "expiresAt":   grant.ExpiresAt.Format(time.RFC3339),
        "timestamp":   time.Now().Format(time.RFC3339),
    }
    eventJSON, _ := json.Marshal(event)
    ctx.GetStub().SetEvent("AccessGranted", eventJSON)

    return nil
}

// RevokeAccess revokes an access grant
func (acc *AccessControlContract) RevokeAccess(
    ctx contractapi.TransactionContextInterface,
    grantID string,
    immediate bool,
    reason string,
) error {
    // Get revoker identity
    revokerID, err := ctx.GetClientIdentity().GetID()
    if err != nil {
        return fmt.Errorf("failed to get revoker identity: %v", err)
    }

    // Find and get the grant
    grant, grantKey, err := acc.findGrant(ctx, grantID)
    if err != nil {
        return fmt.Errorf("failed to find grant: %v", err)
    }

    // Check if grant is already revoked
    if grant.Status == models.AccessStatusRevoked {
        return fmt.Errorf("grant already revoked")
    }

    // Verify revoker has permission (must be grantor or have admin rights)
    if revokerID != grant.GrantorID {
        hasAdminRights, err := acc.checkAdminRights(ctx, revokerID, grant.ResourceID)
        if err != nil || !hasAdminRights {
            return fmt.Errorf("revoker not authorized")
        }
    }

    // Implement immediate revocation or scheduled expiration
    if immediate {
        // Immediate revocation
        grant.Status = models.AccessStatusRevoked
        grant.ExpiresAt = time.Now()
    } else {
        // Scheduled expiration (revoke at end of current day)
        endOfDay := time.Now().Truncate(24*time.Hour).Add(24*time.Hour - time.Second)
        grant.ExpiresAt = endOfDay

        // Create scheduled revocation entry
        scheduleKey := fmt.Sprintf("SCHEDULED_REVOKE~%s", grantID)
        scheduleEntry := map[string]interface{}{
            "grantId":       grantID,
            "scheduledTime": endOfDay.Format(time.RFC3339),
            "reason":        reason,
        }
        scheduleJSON, _ := json.Marshal(scheduleEntry)
        ctx.GetStub().PutState(scheduleKey, scheduleJSON)
    }

    // Update grant
    grantJSON, _ := json.Marshal(grant)
    err = ctx.GetStub().PutState(grantKey, grantJSON)
    if err != nil {
        return fmt.Errorf("failed to update grant: %v", err)
    }

    // Record in access history
    acc.recordAccessHistory(ctx, "GRANT_REVOKED", grantID, revokerID, grant.ResourceID, grant.GranteeID)

    // Clear permission cache
    acc.clearPermissionCache(ctx, grant.GranteeID, grant.ResourceID)

    // Emit event
    event := map[string]interface{}{
        "eventType":  "ACCESS_REVOKED",
        "grantId":    grantID,
        "resourceId": grant.ResourceID,
        "granteeId":  grant.GranteeID,
        "revokerID":  revokerID,
        "immediate":  immediate,
        "reason":     reason,
        "timestamp":  time.Now().Format(time.RFC3339),
    }
    eventJSON, _ := json.Marshal(event)
    ctx.GetStub().SetEvent("AccessRevoked", eventJSON)

    return nil
}

// CheckAccess checks if a user has specific access to a resource
func (acc *AccessControlContract) CheckAccess(
    ctx contractapi.TransactionContextInterface,
    userID string,
    resourceID string,
    action string,
) (bool, error) {
    // Check cache first
    cacheKey := fmt.Sprintf("PERM_CACHE~%s~%s~%s", userID, resourceID, action)
    cachedResult, err := ctx.GetStub().GetState(cacheKey)
    if err == nil && cachedResult != nil {
        // Check if cache is still valid (1 hour)
        var cacheEntry map[string]interface{}
        json.Unmarshal(cachedResult, &cacheEntry)
        if cachedTime, ok := cacheEntry["timestamp"].(string); ok {
            cacheTime, _ := time.Parse(time.RFC3339, cachedTime)
            if time.Since(cacheTime) < time.Hour {
                return cacheEntry["allowed"].(bool), nil
            }
        }
    }

    // Check for emergency override
    emergencyAccess, err := acc.checkEmergencyAccess(ctx, userID, resourceID)
    if err == nil && emergencyAccess {
        acc.recordAccessHistory(ctx, "EMERGENCY_ACCESS", "", userID, resourceID, "")
        return true, nil
    }

    // Get all active grants for user and resource
    resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey(
        utils.PrefixAccess,
        []string{resourceID, userID},
    )
    if err != nil {
        return false, fmt.Errorf("failed to get access grants: %v", err)
    }
    defer resultsIterator.Close()

    // Create permission matrix
    permissionMatrix := make(map[string]bool)

    for resultsIterator.HasNext() {
        queryResponse, err := resultsIterator.Next()
        if err != nil {
            continue
        }

        var grant models.AccessGrant
        err = json.Unmarshal(queryResponse.Value, &grant)
        if err != nil {
            continue
        }

        // Check if grant is active
        if grant.IsActive() {
            // Add permissions to matrix
            for _, perm := range grant.Permissions {
                permissionMatrix[perm] = true
            }
        }
    }

    // Check if requested action is allowed
    allowed := permissionMatrix[action]

    // Cache the result
    cacheEntry := map[string]interface{}{
        "allowed":   allowed,
        "timestamp": time.Now().Format(time.RFC3339),
    }
    cacheJSON, _ := json.Marshal(cacheEntry)
    ctx.GetStub().PutState(cacheKey, cacheJSON)

    // Audit query for compliance reporting
    if allowed {
        acc.recordAccessHistory(ctx, "ACCESS_ALLOWED", "", userID, resourceID, action)
    } else {
        acc.recordAccessHistory(ctx, "ACCESS_DENIED", "", userID, resourceID, action)
    }

    return allowed, nil
}

// QueryAccessGrants queries all access grants for a user
func (acc *AccessControlContract) QueryAccessGrants(
    ctx contractapi.TransactionContextInterface,
    userID string,
) ([]*models.AccessGrant, error) {
    // Get all grants for user
    resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey(
        utils.PrefixUserGrants,
        []string{userID},
    )
    if err != nil {
        return nil, fmt.Errorf("failed to get user grants: %v", err)
    }
    defer resultsIterator.Close()

    var grants []*models.AccessGrant
    grantMap := make(map[string]bool) // To avoid duplicates

    for resultsIterator.HasNext() {
        queryResponse, err := resultsIterator.Next()
        if err != nil {
            continue
        }

        // Extract grant ID from composite key
        _, compositeKeyParts, err := ctx.GetStub().SplitCompositeKey(queryResponse.Key)
        if err != nil || len(compositeKeyParts) < 2 {
            continue
        }

        grantID := compositeKeyParts[1]
        if grantMap[grantID] {
            continue
        }

        // Find the grant
        grant, _, err := acc.findGrant(ctx, grantID)
        if err == nil && grant.IsActive() {
            grants = append(grants, grant)
            grantMap[grantID] = true
        }
    }

    return grants, nil
}

// Helper functions

// validateGranularPermissions validates that the grantor has the permissions they're trying to grant
func (acc *AccessControlContract) validateGranularPermissions(
    ctx contractapi.TransactionContextInterface,
    grantorID string,
    resourceID string,
    permissions []string,
) error {
    // Check if grantor owns the resource or has admin rights
    ownerKey := fmt.Sprintf("RESOURCE_OWNER~%s", resourceID)
    ownerBytes, err := ctx.GetStub().GetState(ownerKey)
    if err == nil && ownerBytes != nil && string(ownerBytes) == grantorID {
        return nil // Owner can grant any permission
    }

    // Check admin rights
    hasAdmin, err := acc.checkAdminRights(ctx, grantorID, resourceID)
    if err == nil && hasAdmin {
        return nil // Admin can grant any permission
    }

    // Check if grantor has all permissions they're trying to grant
    for _, perm := range permissions {
        hasPermission, err := acc.CheckAccess(ctx, grantorID, resourceID, perm)
        if err != nil || !hasPermission {
            return fmt.Errorf("grantor lacks permission: %s", perm)
        }
    }

    return nil
}

// isDelegatedGrant checks if the grant includes delegation permissions
func (acc *AccessControlContract) isDelegatedGrant(permissions []string) bool {
    for _, perm := range permissions {
        if strings.Contains(perm, "delegate") || strings.Contains(perm, "grant") {
            return true
        }
    }
    return false
}

// checkDelegationRights checks if user has delegation rights for a resource
func (acc *AccessControlContract) checkDelegationRights(
    ctx contractapi.TransactionContextInterface,
    userID string,
    resourceID string,
) (bool, error) {
    return acc.CheckAccess(ctx, userID, resourceID, models.PermissionDelegate)
}

// checkAdminRights checks if user has admin rights for a resource
func (acc *AccessControlContract) checkAdminRights(
    ctx contractapi.TransactionContextInterface,
    userID string,
    resourceID string,
) (bool, error) {
    // Check for global admin role
    adminKey := fmt.Sprintf("ADMIN_ROLE~%s", userID)
    adminBytes, err := ctx.GetStub().GetState(adminKey)
    if err == nil && adminBytes != nil && string(adminBytes) == "true" {
        return true, nil
    }

    // Check for resource-specific admin rights
    return acc.CheckAccess(ctx, userID, resourceID, models.PermissionAdmin)
}

// recordAccessHistory records access events for audit
func (acc *AccessControlContract) recordAccessHistory(
    ctx contractapi.TransactionContextInterface,
    action string,
    grantID string,
    actorID string,
    resourceID string,
    targetID string,
) {
    historyEntry := map[string]interface{}{
        "action":     action,
        "grantId":    grantID,
        "actorId":    actorID,
        "resourceId": resourceID,
        "targetId":   targetID,
        "timestamp":  time.Now().Format(time.RFC3339),
        "txId":       ctx.GetStub().GetTxID(),
    }

    historyKey := fmt.Sprintf("ACCESS_HISTORY~%s~%s",
        time.Now().Format("20060102150405"),
        ctx.GetStub().GetTxID())
    historyJSON, _ := json.Marshal(historyEntry)
    ctx.GetStub().PutState(historyKey, historyJSON)
}

// clearPermissionCache clears cached permissions for a user/resource
func (acc *AccessControlContract) clearPermissionCache(
    ctx contractapi.TransactionContextInterface,
    userID string,
    resourceID string,
) {
    // Clear all cached permissions for this user/resource combination
    cachePattern := fmt.Sprintf("PERM_CACHE~%s~%s~", userID, resourceID)
    resultsIterator, err := ctx.GetStub().GetStateByRange(cachePattern, cachePattern+"~")
    if err != nil {
        return
    }
    defer resultsIterator.Close()

    for resultsIterator.HasNext() {
        queryResponse, err := resultsIterator.Next()
        if err != nil {
            continue
        }
        ctx.GetStub().DelState(queryResponse.Key)
    }
}

// checkEmergencyAccess checks if emergency access is granted
func (acc *AccessControlContract) checkEmergencyAccess(
    ctx contractapi.TransactionContextInterface,
    userID string,
    resourceID string,
) (bool, error) {
    // Check for emergency role
    emergencyKey := fmt.Sprintf("EMERGENCY_ACCESS~%s~%s", userID, resourceID)
    emergencyBytes, err := ctx.GetStub().GetState(emergencyKey)
    if err != nil || emergencyBytes == nil {
        return false, nil
    }

    var emergencyGrant map[string]interface{}
    err = json.Unmarshal(emergencyBytes, &emergencyGrant)
    if err != nil {
        return false, err
    }

    // Check if emergency access is still valid
    if expiresAt, ok := emergencyGrant["expiresAt"].(string); ok {
        expTime, err := time.Parse(time.RFC3339, expiresAt)
        if err == nil && time.Now().Before(expTime) {
            return true, nil
        }
    }

    return false, nil
}

// findGrant finds a grant by ID across all resources
func (acc *AccessControlContract) findGrant(
    ctx contractapi.TransactionContextInterface,
    grantID string,
) (*models.AccessGrant, string, error) {
    // Query all grants with this ID
    queryString := fmt.Sprintf(`{
        "selector": {
            "grantId": "%s",
            "objectType": "accessGrant"
        }
    }`, grantID)

    resultsIterator, err := ctx.GetStub().GetQueryResult(queryString)
    if err != nil {
        return nil, "", fmt.Errorf("failed to query grant: %v", err)
    }
    defer resultsIterator.Close()

    if resultsIterator.HasNext() {
        queryResponse, err := resultsIterator.Next()
        if err != nil {
            return nil, "", fmt.Errorf("failed to get grant: %v", err)
        }

        var grant models.AccessGrant
        err = json.Unmarshal(queryResponse.Value, &grant)
        if err != nil {
            return nil, "", fmt.Errorf("failed to unmarshal grant: %v", err)
        }

        return &grant, queryResponse.Key, nil
    }

    return nil, "", fmt.Errorf("grant not found: %s", grantID)
}
