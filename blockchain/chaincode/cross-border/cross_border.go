package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// CrossBorderContract manages cross-border health record sharing
type CrossBorderContract struct {
	contractapi.Contract
}

// CrossBorderVerification represents a cross-border sharing agreement
type CrossBorderVerification struct {
	VerificationID     string   `json:"verificationId"`
	PatientID          string   `json:"patientId"`
	OriginCountry      string   `json:"originCountry"`
	DestinationCountry string   `json:"destinationCountry"`
	HealthRecords      []string `json:"healthRecords"`
	Purpose            string   `json:"purpose"`
	ValidFrom          string   `json:"validFrom"`
	ValidUntil         string   `json:"validUntil"`
	Status             string   `json:"status"`
	RequestingOrg      string   `json:"requestingOrg"`
	ConsentProvided    bool     `json:"consentProvided"`
	DataMinimization   bool     `json:"dataMinimization"`
	EncryptionType     string   `json:"encryptionType"`
	PackageHash        string   `json:"packageHash"`
	CreatedAt          string   `json:"createdAt"`
	UpdatedAt          string   `json:"updatedAt"`
	RevokedAt          string   `json:"revokedAt,omitempty"`
	RevokeReason       string   `json:"revokeReason,omitempty"`
	Metadata           map[string]string `json:"metadata"`
}

// AccessLog represents an access attempt
type AccessLog struct {
	LogID              string `json:"logId"`
	VerificationID     string `json:"verificationId"`
	AccessingCountry   string `json:"accessingCountry"`
	AccessingOrg       string `json:"accessingOrg"`
	AccessTimestamp    string `json:"accessTimestamp"`
	AccessGranted      bool   `json:"accessGranted"`
	Reason             string `json:"reason"`
	IPAddress          string `json:"ipAddress,omitempty"`
	UserAgent          string `json:"userAgent,omitempty"`
}

// CountryPublicKey stores public keys for countries
type CountryPublicKey struct {
	CountryCode string `json:"countryCode"`
	PublicKey   string `json:"publicKey"`
	ValidFrom   string `json:"validFrom"`
	ValidUntil  string `json:"validUntil"`
	Issuer      string `json:"issuer"`
}

// CreateCrossBorderVerification creates a new cross-border verification
func (s *CrossBorderContract) CreateCrossBorderVerification(ctx contractapi.TransactionContextInterface, verificationDataJSON string) error {
	var verificationData map[string]interface{}
	err := json.Unmarshal([]byte(verificationDataJSON), &verificationData)
	if err != nil {
		return fmt.Errorf("failed to unmarshal verification data: %v", err)
	}
	
	// Validate required fields
	verificationID, ok := verificationData["verificationId"].(string)
	if !ok || verificationID == "" {
		return fmt.Errorf("verificationId is required")
	}
	
	patientID, ok := verificationData["patientId"].(string)
	if !ok || patientID == "" {
		return fmt.Errorf("patientId is required")
	}
	
	destinationCountry, ok := verificationData["destinationCountry"].(string)
	if !ok || destinationCountry == "" {
		return fmt.Errorf("destinationCountry is required")
	}
	
	// Extract health records array
	var healthRecords []string
	if records, ok := verificationData["healthRecords"].([]interface{}); ok {
		for _, record := range records {
			if recordStr, ok := record.(string); ok {
				healthRecords = append(healthRecords, recordStr)
			}
		}
	}
	
	// Create verification
	verification := CrossBorderVerification{
		VerificationID:     verificationID,
		PatientID:          patientID,
		OriginCountry:      getStringValue(verificationData, "originCountry"),
		DestinationCountry: destinationCountry,
		HealthRecords:      healthRecords,
		Purpose:            getStringValue(verificationData, "purpose"),
		ValidFrom:          getStringValue(verificationData, "validFrom"),
		ValidUntil:         getStringValue(verificationData, "validUntil"),
		Status:             "pending",
		RequestingOrg:      getStringValue(verificationData, "requestingOrg"),
		ConsentProvided:    getBoolValue(verificationData, "consentProvided"),
		DataMinimization:   getBoolValue(verificationData, "dataMinimization"),
		EncryptionType:     getStringValue(verificationData, "encryptionType"),
		CreatedAt:          time.Now().UTC().Format(time.RFC3339),
		UpdatedAt:          time.Now().UTC().Format(time.RFC3339),
		Metadata:           extractMetadata(verificationData),
	}
	
	// Check if verification already exists
	existingVerification, err := ctx.GetStub().GetState(verificationID)
	if err != nil {
		return fmt.Errorf("failed to check existing verification: %v", err)
	}
	if existingVerification != nil {
		return fmt.Errorf("verification %s already exists", verificationID)
	}
	
	// Store the verification
	verificationJSON, err := json.Marshal(verification)
	if err != nil {
		return err
	}
	
	err = ctx.GetStub().PutState(verificationID, verificationJSON)
	if err != nil {
		return fmt.Errorf("failed to store verification: %v", err)
	}
	
	// Emit event
	eventPayload := map[string]string{
		"verificationId":     verificationID,
		"patientId":          patientID,
		"destinationCountry": destinationCountry,
		"action":             "created",
		"timestamp":          verification.CreatedAt,
	}
	eventJSON, _ := json.Marshal(eventPayload)
	ctx.GetStub().SetEvent("CrossBorderVerificationCreated", eventJSON)
	
	return nil
}

// UpdateCrossBorderVerification updates an existing verification
func (s *CrossBorderContract) UpdateCrossBorderVerification(ctx contractapi.TransactionContextInterface, 
	verificationID string, updateDataJSON string) error {
	
	// Get existing verification
	verificationJSON, err := ctx.GetStub().GetState(verificationID)
	if err != nil {
		return fmt.Errorf("failed to get verification: %v", err)
	}
	if verificationJSON == nil {
		return fmt.Errorf("verification %s does not exist", verificationID)
	}
	
	var verification CrossBorderVerification
	err = json.Unmarshal(verificationJSON, &verification)
	if err != nil {
		return err
	}
	
	// Check if already revoked
	if verification.Status == "revoked" {
		return fmt.Errorf("cannot update revoked verification")
	}
	
	// Parse update data
	var updateData map[string]interface{}
	err = json.Unmarshal([]byte(updateDataJSON), &updateData)
	if err != nil {
		return fmt.Errorf("failed to unmarshal update data: %v", err)
	}
	
	// Update allowed fields
	if newStatus, ok := updateData["status"].(string); ok && newStatus != "" {
		verification.Status = newStatus
	}
	if packageHash, ok := updateData["packageHash"].(string); ok && packageHash != "" {
		verification.PackageHash = packageHash
	}
	
	// Update metadata
	if newMetadata, ok := updateData["metadata"].(map[string]interface{}); ok {
		for k, v := range newMetadata {
			if strVal, ok := v.(string); ok {
				verification.Metadata[k] = strVal
			}
		}
	}
	
	verification.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	
	// Store updated verification
	updatedJSON, err := json.Marshal(verification)
	if err != nil {
		return err
	}
	
	return ctx.GetStub().PutState(verificationID, updatedJSON)
}

// GetCrossBorderVerification retrieves a verification by ID
func (s *CrossBorderContract) GetCrossBorderVerification(ctx contractapi.TransactionContextInterface, 
	verificationID string) (*CrossBorderVerification, error) {
	
	if verificationID == "" {
		return nil, fmt.Errorf("verificationId cannot be empty")
	}
	
	verificationJSON, err := ctx.GetStub().GetState(verificationID)
	if err != nil {
		return nil, fmt.Errorf("failed to read verification: %v", err)
	}
	if verificationJSON == nil {
		return nil, fmt.Errorf("verification %s does not exist", verificationID)
	}
	
	var verification CrossBorderVerification
	err = json.Unmarshal(verificationJSON, &verification)
	if err != nil {
		return nil, err
	}
	
	return &verification, nil
}

// LogCrossBorderAccess logs an access attempt
func (s *CrossBorderContract) LogCrossBorderAccess(ctx contractapi.TransactionContextInterface, 
	verificationID string, accessingCountry string, timestamp string) error {
	
	// Validate inputs
	if verificationID == "" || accessingCountry == "" || timestamp == "" {
		return fmt.Errorf("verificationID, accessingCountry, and timestamp are required")
	}
	
	// Get verification to check validity
	verification, err := s.GetCrossBorderVerification(ctx, verificationID)
	if err != nil {
		return err
	}
	
	// Check if access is allowed
	accessGranted := false
	reason := ""
	
	if verification.Status != "active" {
		reason = fmt.Sprintf("verification status is %s", verification.Status)
	} else if verification.DestinationCountry != accessingCountry {
		reason = "accessing country not authorized"
	} else {
		// Check time validity
		validUntil, err := time.Parse(time.RFC3339, verification.ValidUntil)
		if err == nil && time.Now().UTC().After(validUntil) {
			reason = "verification expired"
		} else {
			accessGranted = true
			reason = "access granted"
		}
	}
	
	// Create access log
	logID := fmt.Sprintf("%s_%s_%d", verificationID, accessingCountry, time.Now().UnixNano())
	accessLog := AccessLog{
		LogID:            logID,
		VerificationID:   verificationID,
		AccessingCountry: accessingCountry,
		AccessTimestamp:  timestamp,
		AccessGranted:    accessGranted,
		Reason:           reason,
	}
	
	// Store access log with composite key
	logKey, err := ctx.GetStub().CreateCompositeKey("accesslog", []string{verificationID, logID})
	if err != nil {
		return fmt.Errorf("failed to create composite key: %v", err)
	}
	
	logJSON, err := json.Marshal(accessLog)
	if err != nil {
		return err
	}
	
	err = ctx.GetStub().PutState(logKey, logJSON)
	if err != nil {
		return fmt.Errorf("failed to store access log: %v", err)
	}
	
	// Emit event
	eventPayload := map[string]string{
		"verificationId":   verificationID,
		"accessingCountry": accessingCountry,
		"accessGranted":    fmt.Sprintf("%t", accessGranted),
		"timestamp":        timestamp,
	}
	eventJSON, _ := json.Marshal(eventPayload)
	ctx.GetStub().SetEvent("CrossBorderAccessLogged", eventJSON)
	
	return nil
}

// RevokeCrossBorderVerification revokes a verification
func (s *CrossBorderContract) RevokeCrossBorderVerification(ctx contractapi.TransactionContextInterface, 
	verificationID string, reason string, timestamp string) error {
	
	// Get existing verification
	verification, err := s.GetCrossBorderVerification(ctx, verificationID)
	if err != nil {
		return err
	}
	
	// Check if already revoked
	if verification.Status == "revoked" {
		return fmt.Errorf("verification already revoked")
	}
	
	// Update verification
	verification.Status = "revoked"
	verification.RevokedAt = timestamp
	verification.RevokeReason = reason
	verification.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	
	// Store updated verification
	verificationJSON, err := json.Marshal(verification)
	if err != nil {
		return err
	}
	
	err = ctx.GetStub().PutState(verificationID, verificationJSON)
	if err != nil {
		return fmt.Errorf("failed to store revoked verification: %v", err)
	}
	
	// Emit event
	eventPayload := map[string]string{
		"verificationId": verificationID,
		"action":         "revoked",
		"reason":         reason,
		"timestamp":      timestamp,
	}
	eventJSON, _ := json.Marshal(eventPayload)
	ctx.GetStub().SetEvent("CrossBorderVerificationRevoked", eventJSON)
	
	return nil
}

// GetCountryPublicKey retrieves the public key for a country
func (s *CrossBorderContract) GetCountryPublicKey(ctx contractapi.TransactionContextInterface, 
	countryCode string) (*CountryPublicKey, error) {
	
	if countryCode == "" {
		return nil, fmt.Errorf("countryCode cannot be empty")
	}
	
	// Create key for country public key
	keyName := fmt.Sprintf("COUNTRY_KEY_%s", countryCode)
	
	keyJSON, err := ctx.GetStub().GetState(keyName)
	if err != nil {
		return nil, fmt.Errorf("failed to read country key: %v", err)
	}
	if keyJSON == nil {
		return nil, fmt.Errorf("public key for country %s does not exist", countryCode)
	}
	
	var countryKey CountryPublicKey
	err = json.Unmarshal(keyJSON, &countryKey)
	if err != nil {
		return nil, err
	}
	
	return &countryKey, nil
}

// SetCountryPublicKey sets the public key for a country
func (s *CrossBorderContract) SetCountryPublicKey(ctx contractapi.TransactionContextInterface, 
	countryCode string, publicKey string, validFrom string, validUntil string, issuer string) error {
	
	// Validate inputs
	if countryCode == "" || publicKey == "" || validFrom == "" || validUntil == "" || issuer == "" {
		return fmt.Errorf("all parameters are required")
	}
	
	// Create country key object
	countryKey := CountryPublicKey{
		CountryCode: countryCode,
		PublicKey:   publicKey,
		ValidFrom:   validFrom,
		ValidUntil:  validUntil,
		Issuer:      issuer,
	}
	
	// Store country key
	keyName := fmt.Sprintf("COUNTRY_KEY_%s", countryCode)
	keyJSON, err := json.Marshal(countryKey)
	if err != nil {
		return err
	}
	
	return ctx.GetStub().PutState(keyName, keyJSON)
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

func extractMetadata(data map[string]interface{}) map[string]string {
	metadata := make(map[string]string)
	if meta, ok := data["metadata"].(map[string]interface{}); ok {
		for k, v := range meta {
			if strVal, ok := v.(string); ok {
				metadata[k] = strVal
			}
		}
	}
	return metadata
}

func main() {
	chaincode, err := contractapi.NewChaincode(&CrossBorderContract{})
	if err != nil {
		fmt.Printf("Error creating cross-border chaincode: %v\n", err)
		return
	}

	if err := chaincode.Start(); err != nil {
		fmt.Printf("Error starting cross-border chaincode: %v\n", err)
	}
}
