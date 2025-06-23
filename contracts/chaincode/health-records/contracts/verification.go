package contracts

import (
    "encoding/json"
    "fmt"
    "time"

    "github.com/haven-health-passport/chaincode/health-records/models"
    "github.com/haven-health-passport/chaincode/health-records/utils"
    "github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// VerificationContract provides functions for managing record verifications
type VerificationContract struct {
    contractapi.Contract
}

// RequestVerification creates a new verification request
func (vc *VerificationContract) RequestVerification(
    ctx contractapi.TransactionContextInterface,
    recordID string,
    verifierID string,
    evidence string,
    comments string,
) error {
    // Generate request ID
    requestID, err := utils.GenerateRecordID()
    if err != nil {
        return fmt.Errorf("failed to generate request ID: %v", err)
    }

    // Get requester identity
    requesterID, err := ctx.GetClientIdentity().GetID()
    if err != nil {
        return fmt.Errorf("failed to get requester identity: %v", err)
    }

    // Validate requester has access to the record
    // This would normally check access permissions
    // For now, we'll assume the requester has access

    // Create verification request
    request := models.NewVerificationRequest(recordID, requesterID, verifierID)
    request.RequestID = requestID
    request.Evidence = evidence
    request.Comments = comments

    // Validate request
    err = utils.ValidateVerificationRequest(request)
    if err != nil {
        return fmt.Errorf("validation failed: %v", err)
    }

    // Store request in world state
    requestKey := fmt.Sprintf("VERIFY_REQUEST~%s", requestID)
    requestJSON, err := json.Marshal(request)
    if err != nil {
        return fmt.Errorf("failed to marshal request: %v", err)
    }

    err = ctx.GetStub().PutState(requestKey, requestJSON)
    if err != nil {
        return fmt.Errorf("failed to store request: %v", err)
    }

    // Add to verification queue (using composite key for indexing)
    queueKey, err := ctx.GetStub().CreateCompositeKey(
        "VERIFY_QUEUE",
        []string{verifierID, requestID},
    )
    if err != nil {
        return fmt.Errorf("failed to create queue key: %v", err)
    }
    err = ctx.GetStub().PutState(queueKey, []byte{0x00})
    if err != nil {
        return fmt.Errorf("failed to add to queue: %v", err)
    }

    // Emit notification event
    notification := map[string]interface{}{
        "eventType":   "VERIFICATION_REQUESTED",
        "requestId":   requestID,
        "recordId":    recordID,
        "requesterId": requesterID,
        "verifierId":  verifierID,
        "timestamp":   time.Now().Format(time.RFC3339),
    }
    notificationJSON, _ := json.Marshal(notification)
    err = ctx.GetStub().SetEvent("VerificationRequested", notificationJSON)
    if err != nil {
        return fmt.Errorf("failed to emit notification: %v", err)
    }

    return nil
}

// ApproveVerification approves a verification request
func (vc *VerificationContract) ApproveVerification(
    ctx contractapi.TransactionContextInterface,
    requestID string,
    signature string,
) error {
    // Get approver identity
    approverID, err := ctx.GetClientIdentity().GetID()
    if err != nil {
        return fmt.Errorf("failed to get approver identity: %v", err)
    }

    // Get verification request
    requestKey := fmt.Sprintf("VERIFY_REQUEST~%s", requestID)
    requestJSON, err := ctx.GetStub().GetState(requestKey)
    if err != nil {
        return fmt.Errorf("failed to get request: %v", err)
    }
    if requestJSON == nil {
        return fmt.Errorf("request not found: %s", requestID)
    }

    var request models.VerificationRequest
    err = json.Unmarshal(requestJSON, &request)
    if err != nil {
        return fmt.Errorf("failed to unmarshal request: %v", err)
    }

    // Check if request is still pending
    if request.Status != models.VerificationStatusPending {
        return fmt.Errorf("request is not pending: current status %s", request.Status)
    }

    // Check approver authorization
    if approverID != request.VerifierID {
        // Check if approver is part of multi-sig group
        multiSigKey := fmt.Sprintf("MULTISIG~%s", request.VerifierID)
        multiSigJSON, _ := ctx.GetStub().GetState(multiSigKey)
        if multiSigJSON == nil {
            return fmt.Errorf("approver not authorized: %s", approverID)
        }

        // For now, we'll allow if multi-sig exists
        // In production, we'd check specific authorization rules
    }

    // Check time constraints (72 hour window)
    requestAge := time.Since(request.RequestedAt)
    if requestAge > 72*time.Hour {
        return fmt.Errorf("request has expired (older than 72 hours)")
    }

    // Generate verification ID
    verificationID, err := utils.GenerateRecordID()
    if err != nil {
        return fmt.Errorf("failed to generate verification ID: %v", err)
    }

    // Create verification status
    verification := models.NewVerificationStatus(verificationID, request.RecordID, approverID)
    verification.Signature = signature

    // Store verification
    verificationKey := utils.CreateVerificationKey(request.RecordID, verificationID)
    verificationJSON, err := json.Marshal(verification)
    if err != nil {
        return fmt.Errorf("failed to marshal verification: %v", err)
    }

    err = ctx.GetStub().PutState(verificationKey, verificationJSON)
    if err != nil {
        return fmt.Errorf("failed to store verification: %v", err)
    }

    // Update request status
    request.Status = models.VerificationStatusApproved
    updatedRequestJSON, _ := json.Marshal(request)
    ctx.GetStub().PutState(requestKey, updatedRequestJSON)

    // Remove from verification queue
    queueKey, _ := ctx.GetStub().CreateCompositeKey(
        "VERIFY_QUEUE",
        []string{request.VerifierID, requestID},
    )
    ctx.GetStub().DelState(queueKey)

    // Update health record with verification
    vc.updateRecordVerification(ctx, request.RecordID, verificationID)

    // Create approval workflow audit entry
    auditEntry := map[string]interface{}{
        "action":         "VERIFICATION_APPROVED",
        "requestId":      requestID,
        "verificationId": verificationID,
        "approverID":     approverID,
        "timestamp":      time.Now().Format(time.RFC3339),
        "signature":      signature,
    }
    auditKey := fmt.Sprintf("AUDIT~VERIFY~%s~%s", requestID, time.Now().Format("20060102150405"))
    auditJSON, _ := json.Marshal(auditEntry)
    ctx.GetStub().PutState(auditKey, auditJSON)

    // Emit event
    event := map[string]interface{}{
        "eventType":      "VERIFICATION_APPROVED",
        "requestId":      requestID,
        "verificationId": verificationID,
        "recordId":       request.RecordID,
        "approverID":     approverID,
        "timestamp":      time.Now().Format(time.RFC3339),
    }
    eventJSON, _ := json.Marshal(event)
    ctx.GetStub().SetEvent("VerificationApproved", eventJSON)

    return nil
}

// RejectVerification rejects a verification request
func (vc *VerificationContract) RejectVerification(
    ctx contractapi.TransactionContextInterface,
    requestID string,
    reason string,
) error {
    // Get rejector identity
    rejectorID, err := ctx.GetClientIdentity().GetID()
    if err != nil {
        return fmt.Errorf("failed to get rejector identity: %v", err)
    }

    // Get verification request
    requestKey := fmt.Sprintf("VERIFY_REQUEST~%s", requestID)
    requestJSON, err := ctx.GetStub().GetState(requestKey)
    if err != nil {
        return fmt.Errorf("failed to get request: %v", err)
    }
    if requestJSON == nil {
        return fmt.Errorf("request not found: %s", requestID)
    }

    var request models.VerificationRequest
    err = json.Unmarshal(requestJSON, &request)
    if err != nil {
        return fmt.Errorf("failed to unmarshal request: %v", err)
    }

    // Check if request is still pending
    if request.Status != models.VerificationStatusPending {
        return fmt.Errorf("request is not pending: current status %s", request.Status)
    }

    // Check rejector authorization
    if rejectorID != request.VerifierID {
        return fmt.Errorf("rejector not authorized: %s", rejectorID)
    }

    // Update request status
    request.Status = models.VerificationStatusRejected
    request.Comments = fmt.Sprintf("%s | Rejection reason: %s", request.Comments, reason)

    updatedRequestJSON, _ := json.Marshal(request)
    err = ctx.GetStub().PutState(requestKey, updatedRequestJSON)
    if err != nil {
        return fmt.Errorf("failed to update request: %v", err)
    }

    // Remove from verification queue
    queueKey, _ := ctx.GetStub().CreateCompositeKey(
        "VERIFY_QUEUE",
        []string{request.VerifierID, requestID},
    )
    ctx.GetStub().DelState(queueKey)

    // Create appeal process entry
    appealKey := fmt.Sprintf("APPEAL~%s", requestID)
    appealEntry := map[string]interface{}{
        "requestId":    requestID,
        "recordId":     request.RecordID,
        "status":       "available",
        "rejectionDate": time.Now().Format(time.RFC3339),
        "reason":       reason,
        "appealDeadline": time.Now().Add(7 * 24 * time.Hour).Format(time.RFC3339), // 7 days to appeal
    }
    appealJSON, _ := json.Marshal(appealEntry)
    ctx.GetStub().PutState(appealKey, appealJSON)

    // Create audit entry
    auditEntry := map[string]interface{}{
        "action":     "VERIFICATION_REJECTED",
        "requestId":  requestID,
        "rejectorID": rejectorID,
        "reason":     reason,
        "timestamp":  time.Now().Format(time.RFC3339),
    }
    auditKey := fmt.Sprintf("AUDIT~VERIFY~%s~%s", requestID, time.Now().Format("20060102150405"))
    auditJSON, _ := json.Marshal(auditEntry)
    ctx.GetStub().PutState(auditKey, auditJSON)

    // Send notification event
    notification := map[string]interface{}{
        "eventType":   "VERIFICATION_REJECTED",
        "requestId":   requestID,
        "recordId":    request.RecordID,
        "requesterId": request.RequesterID,
        "rejectorID":  rejectorID,
        "reason":      reason,
        "appealDeadline": time.Now().Add(7 * 24 * time.Hour).Format(time.RFC3339),
        "timestamp":   time.Now().Format(time.RFC3339),
    }
    notificationJSON, _ := json.Marshal(notification)
    ctx.GetStub().SetEvent("VerificationRejected", notificationJSON)

    return nil
}

// RevokeVerification revokes an existing verification
func (vc *VerificationContract) RevokeVerification(
    ctx contractapi.TransactionContextInterface,
    verificationID string,
    recordID string,
    reason string,
    immediate bool,
) error {
    // Get revoker identity
    revokerID, err := ctx.GetClientIdentity().GetID()
    if err != nil {
        return fmt.Errorf("failed to get revoker identity: %v", err)
    }

    // Get verification
    verificationKey := utils.CreateVerificationKey(recordID, verificationID)
    verificationJSON, err := ctx.GetStub().GetState(verificationKey)
    if err != nil {
        return fmt.Errorf("failed to get verification: %v", err)
    }
    if verificationJSON == nil {
        return fmt.Errorf("verification not found: %s", verificationID)
    }

    var verification models.VerificationStatus
    err = json.Unmarshal(verificationJSON, &verification)
    if err != nil {
        return fmt.Errorf("failed to unmarshal verification: %v", err)
    }

    // Check if already revoked
    if verification.Status == models.VerificationStatusRevoked {
        return fmt.Errorf("verification already revoked")
    }

    // Check revoker authorization
    if revokerID != verification.VerifierID {
        // Check if revoker has admin privileges
        // This would normally check against access control policies
        return fmt.Errorf("revoker not authorized: %s", revokerID)
    }

    // Implement grace period (24 hours) unless immediate revocation
    var effectiveRevocationTime time.Time
    if immediate {
        effectiveRevocationTime = time.Now()
    } else {
        effectiveRevocationTime = time.Now().Add(24 * time.Hour)

        // Create grace period notification
        graceNotification := map[string]interface{}{
            "verificationId": verificationID,
            "recordId":       recordID,
            "scheduledRevocation": effectiveRevocationTime.Format(time.RFC3339),
            "reason":         reason,
        }
        graceKey := fmt.Sprintf("GRACE_PERIOD~%s", verificationID)
        graceJSON, _ := json.Marshal(graceNotification)
        ctx.GetStub().PutState(graceKey, graceJSON)
    }

    // Create revocation entry
    revocationEntry := map[string]interface{}{
        "verificationId": verificationID,
        "recordId":       recordID,
        "revokerID":      revokerID,
        "reason":         reason,
        "revocationDate": time.Now().Format(time.RFC3339),
        "effectiveDate":  effectiveRevocationTime.Format(time.RFC3339),
        "immediate":      immediate,
    }
    revocationKey := fmt.Sprintf("REVOCATION~%s", verificationID)
    revocationJSON, _ := json.Marshal(revocationEntry)
    ctx.GetStub().PutState(revocationKey, revocationJSON)

    // If immediate, update verification status now
    if immediate {
        verification.Status = models.VerificationStatusRevoked
        updatedJSON, _ := json.Marshal(verification)
        ctx.GetStub().PutState(verificationKey, updatedJSON)

        // Cascade logic - remove verification from health record
        vc.removeRecordVerification(ctx, recordID, verificationID)
    }

    // Create restoration process entry
    restorationEntry := map[string]interface{}{
        "verificationId": verificationID,
        "recordId":       recordID,
        "status":         "available",
        "revocationDate": time.Now().Format(time.RFC3339),
        "restorationDeadline": time.Now().Add(30 * 24 * time.Hour).Format(time.RFC3339), // 30 days to request restoration
    }
    restorationKey := fmt.Sprintf("RESTORATION~%s", verificationID)
    restorationJSON, _ := json.Marshal(restorationEntry)
    ctx.GetStub().PutState(restorationKey, restorationJSON)

    // Audit logging
    auditEntry := map[string]interface{}{
        "action":         "VERIFICATION_REVOKED",
        "verificationId": verificationID,
        "recordId":       recordID,
        "revokerID":      revokerID,
        "reason":         reason,
        "immediate":      immediate,
        "effectiveDate":  effectiveRevocationTime.Format(time.RFC3339),
        "timestamp":      time.Now().Format(time.RFC3339),
    }
    auditKey := fmt.Sprintf("AUDIT~REVOKE~%s~%s", verificationID, time.Now().Format("20060102150405"))
    auditJSON, _ := json.Marshal(auditEntry)
    ctx.GetStub().PutState(auditKey, auditJSON)

    // Emit event
    event := map[string]interface{}{
        "eventType":      "VERIFICATION_REVOKED",
        "verificationId": verificationID,
        "recordId":       recordID,
        "revokerID":      revokerID,
        "reason":         reason,
        "immediate":      immediate,
        "effectiveDate":  effectiveRevocationTime.Format(time.RFC3339),
        "timestamp":      time.Now().Format(time.RFC3339),
    }
    eventJSON, _ := json.Marshal(event)
    ctx.GetStub().SetEvent("VerificationRevoked", eventJSON)

    return nil
}

// QueryVerificationStatus queries the verification status of a record
func (vc *VerificationContract) QueryVerificationStatus(
    ctx contractapi.TransactionContextInterface,
    recordID string,
) (*models.VerificationStatus, error) {
    // Get all verifications for the record
    resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey(
        utils.PrefixVerification,
        []string{recordID},
    )
    if err != nil {
        return nil, fmt.Errorf("failed to get verifications: %v", err)
    }
    defer resultsIterator.Close()

    var latestVerification *models.VerificationStatus
    var latestTime time.Time

    // Find the most recent valid verification
    for resultsIterator.HasNext() {
        queryResponse, err := resultsIterator.Next()
        if err != nil {
            return nil, fmt.Errorf("failed to iterate: %v", err)
        }

        var verification models.VerificationStatus
        err = json.Unmarshal(queryResponse.Value, &verification)
        if err != nil {
            continue
        }

        // Check if verification is valid
        if verification.IsValid() && verification.VerifiedAt.After(latestTime) {
            latestVerification = &verification
            latestTime = verification.VerifiedAt
        }
    }

    if latestVerification == nil {
        return nil, fmt.Errorf("no valid verification found for record: %s", recordID)
    }

    return latestVerification, nil
}

// updateRecordVerification adds a verification ID to a health record
func (vc *VerificationContract) updateRecordVerification(
    ctx contractapi.TransactionContextInterface,
    recordID string,
    verificationID string,
) error {
    // This is a simplified version - in production, we'd need to know the full record key
    // For now, we'll store a mapping
    mappingKey := fmt.Sprintf("RECORD_VERIFY_MAP~%s~%s", recordID, verificationID)
    err := ctx.GetStub().PutState(mappingKey, []byte{0x00})
    if err != nil {
        return fmt.Errorf("failed to update record verification: %v", err)
    }
    return nil
}

// removeRecordVerification removes a verification ID from a health record
func (vc *VerificationContract) removeRecordVerification(
    ctx contractapi.TransactionContextInterface,
    recordID string,
    verificationID string,
) error {
    // Remove the mapping
    mappingKey := fmt.Sprintf("RECORD_VERIFY_MAP~%s~%s", recordID, verificationID)
    err := ctx.GetStub().DelState(mappingKey)
    if err != nil {
        return fmt.Errorf("failed to remove record verification: %v", err)
    }
    return nil
}

// QueryPendingVerifications queries all pending verification requests for a verifier
func (vc *VerificationContract) QueryPendingVerifications(
    ctx contractapi.TransactionContextInterface,
    verifierID string,
) ([]*models.VerificationRequest, error) {
    // Get verification queue for verifier
    resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey(
        "VERIFY_QUEUE",
        []string{verifierID},
    )
    if err != nil {
        return nil, fmt.Errorf("failed to get verification queue: %v", err)
    }
    defer resultsIterator.Close()

    var requests []*models.VerificationRequest

    for resultsIterator.HasNext() {
        queryResponse, err := resultsIterator.Next()
        if err != nil {
            return nil, fmt.Errorf("failed to iterate: %v", err)
        }

        // Extract request ID from composite key
        _, compositeKeyParts, err := ctx.GetStub().SplitCompositeKey(queryResponse.Key)
        if err != nil {
            continue
        }

        if len(compositeKeyParts) >= 2 {
            requestID := compositeKeyParts[1]

            // Get the request
            requestKey := fmt.Sprintf("VERIFY_REQUEST~%s", requestID)
            requestJSON, err := ctx.GetStub().GetState(requestKey)
            if err != nil || requestJSON == nil {
                continue
            }

            var request models.VerificationRequest
            err = json.Unmarshal(requestJSON, &request)
            if err == nil && request.Status == models.VerificationStatusPending {
                requests = append(requests, &request)
            }
        }
    }

    return requests, nil
}
