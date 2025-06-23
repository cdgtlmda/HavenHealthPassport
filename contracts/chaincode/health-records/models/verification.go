package models

import (
    "time"
)

// VerificationRequest represents a request for record verification
type VerificationRequest struct {
    RequestID    string    `json:"requestId"`
    RecordID     string    `json:"recordId"`
    RequesterID  string    `json:"requesterId"`
    VerifierID   string    `json:"verifierId"`
    RequestedAt  time.Time `json:"requestedAt"`
    Status       string    `json:"status"`
    Evidence     string    `json:"evidence"`
    Comments     string    `json:"comments"`
    ObjectType   string    `json:"objectType"`
}

// VerificationStatus represents the verification status of a record
type VerificationStatus struct {
    VerificationID string    `json:"verificationId"`
    RecordID       string    `json:"recordId"`
    VerifierID     string    `json:"verifierId"`
    VerifiedAt     time.Time `json:"verifiedAt"`
    ExpiresAt      time.Time `json:"expiresAt"`
    Status         string    `json:"status"`
    Signature      string    `json:"signature"`
    ObjectType     string    `json:"objectType"`
}

// Verification status constants
const (
    VerificationStatusPending  = "pending"
    VerificationStatusApproved = "approved"
    VerificationStatusRejected = "rejected"
    VerificationStatusRevoked  = "revoked"
    VerificationStatusExpired  = "expired"
)

// NewVerificationRequest creates a new verification request
func NewVerificationRequest(recordID, requesterID, verifierID string) *VerificationRequest {
    return &VerificationRequest{
        RecordID:    recordID,
        RequesterID: requesterID,
        VerifierID:  verifierID,
        RequestedAt: time.Now(),
        Status:      VerificationStatusPending,
        ObjectType:  "verificationRequest",
    }
}

// NewVerificationStatus creates a new verification status
func NewVerificationStatus(verificationID, recordID, verifierID string) *VerificationStatus {
    return &VerificationStatus{
        VerificationID: verificationID,
        RecordID:       recordID,
        VerifierID:     verifierID,
        VerifiedAt:     time.Now(),
        ExpiresAt:      time.Now().Add(365 * 24 * time.Hour), // 1 year default
        Status:         VerificationStatusApproved,
        ObjectType:     "verificationStatus",
    }
}

// IsExpired checks if the verification has expired
func (vs *VerificationStatus) IsExpired() bool {
    return time.Now().After(vs.ExpiresAt)
}

// IsValid checks if the verification is valid (approved and not expired)
func (vs *VerificationStatus) IsValid() bool {
    return vs.Status == VerificationStatusApproved && !vs.IsExpired()
}
