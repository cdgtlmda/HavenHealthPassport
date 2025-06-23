package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// AccessControlContract manages access permissions for health records
type AccessControlContract struct {
	contractapi.Contract
}

// AccessGrant represents an access permission grant
type AccessGrant struct {
	GrantID          string            `json:"grantId"`
	PatientID        string            `json:"patientId"`
	GranteeID        string            `json:"granteeId"`
	GranteeType      string            `json:"granteeType"`
	GrantorID        string            `json:"grantorId"`
	Permissions      []string          `json:"permissions"`
	ResourceTypes    []string          `json:"resourceTypes"`
	ResourceIDs      []string          `json:"resourceIds,omitempty"`
	ValidFrom        string            `json:"validFrom"`
	ValidUntil       string            `json:"validUntil"`
	Status           string            `json:"status"`
	Purpose          string            `json:"purpose"`
	CanDelegate      bool              `json:"canDelegate"`
	DelegationLevel  int               `json:"delegationLevel"`
	CreatedAt        string            `json:"createdAt"`
	UpdatedAt        string            `json:"updatedAt"`
	RevokedAt        string            `json:"revokedAt,omitempty"`
	RevokedBy        string            `json:"revokedBy,omitempty"`
	RevocationReason string            `json:"revocationReason,omitempty"`
	Conditions       map[string]string `json:"conditions,omitempty"`
	Metadata         map[string]string `json:"metadata"`
}

// AccessCheckResult represents the result of an access check
type AccessCheckResult struct {
	Allowed       bool     `json:"allowed"`
	GrantID       string   `json:"grantId,omitempty"`
	Permissions   []string `json:"permissions,omitempty"`
	Reason        string   `json:"reason"`
	CheckedAt     string   `json:"checkedAt"`
	ValidUntil    string   `json:"validUntil,omitempty"`
}

// AuditEntry represents an access audit log entry
type AuditEntry struct {
	AuditID       string            `json:"auditId"`
	Action        string            `json:"action"`
	ActorID       string            `json:"actorId"`
	ResourceID    string            `json:"resourceId"`
	ResourceType  string            `json:"resourceType"`
	GrantID       string            `json:"grantId,omitempty"`
	Timestamp     string            `json:"timestamp"`
	Success       bool              `json:"success"`
	Reason        string            `json:"reason,omitempty"`
	IPAddress     string            `json:"ipAddress,omitempty"`
	Metadata      map[string]string `json:"metadata,omitempty"`
}

// GrantAccess creates a new access grant
func (s *AccessControlContract) GrantAccess(ctx contractapi.TransactionContextInterface, grantDataJSON string) error {
	var grantData map[string]interface{}
	err := json.Unmarshal([]byte(grantDataJSON), &grantData)
	if err != nil {
		return fmt.Errorf("failed to unmarshal grant data: %v", err)
	}
	
	// Validate required fields
	patientID, ok := grantData["patientId"].(string)
	if !ok || patientID == "" {
		return fmt.Errorf("patientId is required")
	}
	
	granteeID, ok := grantData["granteeId"].(string)
	if !ok || granteeID == "" {
		return fmt.Errorf("granteeId is required")
	}
	
	grantorID, ok := grantData["grantorId"].(string)
	if !ok || grantorID == "" {
		return fmt.Errorf("grantorId is required")
	}
	
	// Extract permissions array
	permissions := extractStringArray(grantData, "permissions")
	if len(permissions) == 0 {
		return fmt.Errorf("at least one permission is required")
	}
	
	// Extract resource types
	resourceTypes := extractStringArray(grantData, "resourceTypes")
	if len(resourceTypes) == 0 {
		return fmt.Errorf("at least one resource type is required")
	}
	
	// Generate grant ID
	grantID := fmt.Sprintf("GRANT_%s_%s_%d", patientID, granteeID, time.Now().UnixNano())
	
	// Create access grant
	grant := AccessGrant{
		GrantID:         grantID,
		PatientID:       patientID,
		GranteeID:       granteeID,
		GranteeType:     getStringValue(grantData, "granteeType"),
		GrantorID:       grantorID,
		Permissions:     permissions,
		ResourceTypes:   resourceTypes,
		ResourceIDs:     extractStringArray(grantData, "resourceIds"),
		ValidFrom:       getStringValue(grantData, "validFrom"),
		ValidUntil:      getStringValue(grantData, "validUntil"),
		Status:          "active",
		Purpose:         getStringValue(grantData, "purpose"),
		CanDelegate:     getBoolValue(grantData, "canDelegate"),
		DelegationLevel: getIntValue(grantData, "delegationLevel"),
		CreatedAt:       time.Now().UTC().Format(time.RFC3339),
		UpdatedAt:       time.Now().UTC().Format(time.RFC3339),
		Conditions:      extractStringMap(grantData, "conditions"),
		Metadata:        extractStringMap(grantData, "metadata"),
	}
	
	// Validate time constraints
	if grant.ValidFrom != "" && grant.ValidUntil != "" {
		validFrom, err1 := time.Parse(time.RFC3339, grant.ValidFrom)
		validUntil, err2 := time.Parse(time.RFC3339, grant.ValidUntil)
		if err1 == nil && err2 == nil && validFrom.After(validUntil) {
			return fmt.Errorf("validFrom cannot be after validUntil")
		}
	}
	
	// Store the grant
	grantJSON, err := json.Marshal(grant)
	if err != nil {
		return err
	}
	
	err = ctx.GetStub().PutState(grantID, grantJSON)
	if err != nil {
		return fmt.Errorf("failed to store grant: %v", err)
	}
	
	// Create composite key for patient's grants
	patientGrantKey, err := ctx.GetStub().CreateCompositeKey("patient~grant", []string{patientID, grantID})
	if err != nil {
		return fmt.Errorf("failed to create patient grant key: %v", err)
	}
	ctx.GetStub().PutState(patientGrantKey, []byte{0x00})
	
	// Create composite key for grantee's grants
	granteeGrantKey, err := ctx.GetStub().CreateCompositeKey("grantee~grant", []string{granteeID, grantID})
	if err != nil {
		return fmt.Errorf("failed to create grantee grant key: %v", err)
	}
	ctx.GetStub().PutState(granteeGrantKey, []byte{0x00})
	
	// Log audit entry
	s.logAuditEntry(ctx, "grant_access", grantorID, patientID, "patient", grantID, true, "access granted")
	
	// Emit event
	eventPayload := map[string]string{
		"grantId":    grantID,
		"patientId":  patientID,
		"granteeId":  granteeID,
		"action":     "granted",
		"timestamp":  grant.CreatedAt,
	}
	eventJSON, _ := json.Marshal(eventPayload)
	ctx.GetStub().SetEvent("AccessGranted", eventJSON)
	
	return nil
}

// RevokeAccess revokes an existing access grant
func (s *AccessControlContract) RevokeAccess(ctx contractapi.TransactionContextInterface, 
	grantID string, revokedBy string, reason string) error {
	
	// Get existing grant
	grantJSON, err := ctx.GetStub().GetState(grantID)
	if err != nil {
		return fmt.Errorf("failed to get grant: %v", err)
	}
	if grantJSON == nil {
		return fmt.Errorf("grant %s does not exist", grantID)
	}
	
	var grant AccessGrant
	err = json.Unmarshal(grantJSON, &grant)
	if err != nil {
		return err
	}
	
	// Check if already revoked
	if grant.Status == "revoked" {
		return fmt.Errorf("grant already revoked")
	}
	
	// Update grant
	grant.Status = "revoked"
	grant.RevokedAt = time.Now().UTC().Format(time.RFC3339)
	grant.RevokedBy = revokedBy
	grant.RevocationReason = reason
	grant.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	
	// Store updated grant
	updatedJSON, err := json.Marshal(grant)
	if err != nil {
		return err
	}
	
	err = ctx.GetStub().PutState(grantID, updatedJSON)
	if err != nil {
		return fmt.Errorf("failed to store revoked grant: %v", err)
	}
	
	// Log audit entry
	s.logAuditEntry(ctx, "revoke_access", revokedBy, grant.PatientID, "patient", grantID, true, reason)
	
	// Emit event
	eventPayload := map[string]string{
		"grantId":   grantID,
		"patientId": grant.PatientID,
		"granteeId": grant.GranteeID,
		"action":    "revoked",
		"reason":    reason,
		"timestamp": grant.RevokedAt,
	}
	eventJSON, _ := json.Marshal(eventPayload)
	ctx.GetStub().SetEvent("AccessRevoked", eventJSON)
	
	return nil
}

// CheckAccess checks if a grantee has access to a resource
func (s *AccessControlContract) CheckAccess(ctx contractapi.TransactionContextInterface, 
	granteeID string, patientID string, resourceType string, permission string) (*AccessCheckResult, error) {
	
	// Get all grants for this grantee-patient combination
	resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey("grantee~grant", []string{granteeID})
	if err != nil {
		return nil, fmt.Errorf("failed to get grants: %v", err)
	}
	defer resultsIterator.Close()
	
	currentTime := time.Now().UTC()
	
	for resultsIterator.HasNext() {
		queryResponse, err := resultsIterator.Next()
		if err != nil {
			return nil, err
		}
		
		// Extract grant ID from composite key
		_, compositeKeyParts, err := ctx.GetStub().SplitCompositeKey(queryResponse.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		grantID := compositeKeyParts[1]
		
		// Get grant details
		grantJSON, err := ctx.GetStub().GetState(grantID)
		if err != nil || grantJSON == nil {
			continue
		}
		
		var grant AccessGrant
		err = json.Unmarshal(grantJSON, &grant)
		if err != nil {
			continue
		}
		
		// Check if grant matches patient and is active
		if grant.PatientID != patientID || grant.Status != "active" {
			continue
		}
		
		// Check time validity
		if grant.ValidFrom != "" {
			validFrom, err := time.Parse(time.RFC3339, grant.ValidFrom)
			if err == nil && currentTime.Before(validFrom) {
				continue
			}
		}
		
		if grant.ValidUntil != "" {
			validUntil, err := time.Parse(time.RFC3339, grant.ValidUntil)
			if err == nil && currentTime.After(validUntil) {
				continue
			}
		}
		
		// Check resource type
		resourceTypeMatch := false
		for _, rt := range grant.ResourceTypes {
			if rt == resourceType || rt == "*" || rt == "all" {
				resourceTypeMatch = true
				break
			}
		}
		if !resourceTypeMatch {
			continue
		}
		
		// Check permission
		permissionMatch := false
		for _, p := range grant.Permissions {
			if p == permission || p == "*" || p == "all" {
				permissionMatch = true
				break
			}
		}
		if !permissionMatch {
			continue
		}
		
		// Access granted
		result := &AccessCheckResult{
			Allowed:     true,
			GrantID:     grantID,
			Permissions: grant.Permissions,
			Reason:      "access granted",
			CheckedAt:   currentTime.Format(time.RFC3339),
			ValidUntil:  grant.ValidUntil,
		}
		
		// Log audit entry
		s.logAuditEntry(ctx, "check_access", granteeID, patientID, resourceType, grantID, true, "access allowed")
		
		return result, nil
	}
	
	// No matching grant found
	result := &AccessCheckResult{
		Allowed:   false,
		Reason:    "no matching grant found",
		CheckedAt: currentTime.Format(time.RFC3339),
	}
	
	// Log audit entry
	s.logAuditEntry(ctx, "check_access", granteeID, patientID, resourceType, "", false, "access denied")
	
	return result, nil
}

// GetAccessHistory retrieves access history for a patient
func (s *AccessControlContract) GetAccessHistory(ctx contractapi.TransactionContextInterface, 
	patientID string) ([]*AccessGrant, error) {
	
	// Get all grants for this patient
	resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey("patient~grant", []string{patientID})
	if err != nil {
		return nil, fmt.Errorf("failed to get grants: %v", err)
	}
	defer resultsIterator.Close()
	
	var grants []*AccessGrant
	
	for resultsIterator.HasNext() {
		queryResponse, err := resultsIterator.Next()
		if err != nil {
			return nil, err
		}
		
		// Extract grant ID from composite key
		_, compositeKeyParts, err := ctx.GetStub().SplitCompositeKey(queryResponse.Key)
		if err != nil || len(compositeKeyParts) < 2 {
			continue
		}
		grantID := compositeKeyParts[1]
		
		// Get grant details
		grantJSON, err := ctx.GetStub().GetState(grantID)
		if err != nil || grantJSON == nil {
			continue
		}
		
		var grant AccessGrant
		err = json.Unmarshal(grantJSON, &grant)
		if err != nil {
			continue
		}
		
		grants = append(grants, &grant)
	}
	
	return grants, nil
}

// Helper function to log audit entries
func (s *AccessControlContract) logAuditEntry(ctx contractapi.TransactionContextInterface, 
	action string, actorID string, resourceID string, resourceType string, 
	grantID string, success bool, reason string) {
	
	auditID := fmt.Sprintf("AUDIT_%s_%d", actorID, time.Now().UnixNano())
	
	audit := AuditEntry{
		AuditID:      auditID,
		Action:       action,
		ActorID:      actorID,
		ResourceID:   resourceID,
		ResourceType: resourceType,
		GrantID:      grantID,
		Timestamp:    time.Now().UTC().Format(time.RFC3339),
		Success:      success,
		Reason:       reason,
	}
	
	// Store audit entry with composite key
	auditKey, err := ctx.GetStub().CreateCompositeKey("audit", []string{resourceID, auditID})
	if err == nil {
		auditJSON, _ := json.Marshal(audit)
		ctx.GetStub().PutState(auditKey, auditJSON)
	}
}

// Helper functions
func getStringValue(data map[string]interface{}, key string) string {
	if val, ok := data[key].(string); ok {
		return val
	}
	return ""
}

func getBoolValue(data map[string]interface{}, key string) bool {
	if val, ok := data[key].(bool); ok {
		return val
	}
	return false
}

func getIntValue(data map[string]interface{}, key string) int {
	if val, ok := data[key].(float64); ok {
		return int(val)
	}
	return 0
}

func extractStringArray(data map[string]interface{}, key string) []string {
	var result []string
	if arr, ok := data[key].([]interface{}); ok {
		for _, item := range arr {
			if str, ok := item.(string); ok {
				result = append(result, str)
			}
		}
	}
	return result
}

func extractStringMap(data map[string]interface{}, key string) map[string]string {
	result := make(map[string]string)
	if m, ok := data[key].(map[string]interface{}); ok {
		for k, v := range m {
			if str, ok := v.(string); ok {
				result[k] = str
			}
		}
	}
	return result
}

func main() {
	chaincode, err := contractapi.NewChaincode(&AccessControlContract{})
	if err != nil {
		fmt.Printf("Error creating access control chaincode: %v\n", err)
		return
	}

	if err := chaincode.Start(); err != nil {
		fmt.Printf("Error starting access control chaincode: %v\n", err)
	}
}
