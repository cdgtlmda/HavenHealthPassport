# Verification Workflow Usage Guide

## Overview

The Haven Health Passport verification workflow system provides a comprehensive state machine for managing the verification process of patient identities and medical records.

## Workflow States

- **DRAFT**: Initial state when verification is being prepared
- **SUBMITTED**: Verification has been submitted for review
- **UNDER_REVIEW**: Verification is being actively reviewed
- **ADDITIONAL_INFO_REQUIRED**: Reviewer has requested more information
- **PENDING_APPROVAL**: Awaiting approval from authorized personnel
- **APPROVED**: Verification has been approved
- **REJECTED**: Verification has been rejected
- **EXPIRED**: Verification workflow has expired
- **REVOKED**: Verification has been revoked
- **COMPLETED**: Verification process is complete

## GraphQL Operations

### Creating a Workflow

```graphql
mutation CreateVerificationWorkflow {
  workflow {
    createWorkflow(input: {
      verificationId: "123e4567-e89b-12d3-a456-426614174000",
      workflowType: "identity_verification",
      metadata: {
        priority: "high",
        requestedBy: "UNHCR"
      }
    }) {
      success
      message
      workflowStatus {
        id
        state
        currentStep {
          name
          description
          dueDate
        }
        completionPercentage
      }
    }
  }
}
```

### Transitioning Workflow State

```graphql
mutation TransitionWorkflow {
  workflow {
    transitionWorkflow(input: {
      verificationId: "123e4567-e89b-12d3-a456-426614174000",
      action: SUBMIT,
      reason: "All documents collected"
    }) {
      success
      message
      workflowStatus {
        state
        transitions {
          fromState
          toState
          action
          performedAt
        }
      }
    }
  }
}
```

### Creating an Approval Chain

```graphql
mutation CreateApprovalChain {
  workflow {
    createApprovalChain(input: {
      verificationId: "123e4567-e89b-12d3-a456-426614174000",
      chainName: "High Level Identity Verification",
      steps: [
        { role: "field_officer", required: true },
        { role: "supervisor", required: true },
        { role: "security_officer", required: false }
      ]
    }) {
      success
      message
    }
  }
}
```

### Querying Workflow Status

```graphql
query GetWorkflowStatus {
  workflow {
    workflowStatus(verificationId: "123e4567-e89b-12d3-a456-426614174000") {
      id
      state
      createdAt
      updatedAt
      currentStep {
        name
        description
        state
        assignedTo
        dueDate
        completed
      }
      completionPercentage
      approvalChain {
        name
        currentStep
        steps {
          order
          role
          approved
          approvedAt
          comments
        }
      }
    }
  }
}
```

## Workflow Actions

Available actions for state transitions:

- **CREATE**: Create a new workflow
- **SUBMIT**: Submit for review
- **ASSIGN_REVIEWER**: Assign to a reviewer
- **START_REVIEW**: Begin the review process
- **REQUEST_INFO**: Request additional information
- **PROVIDE_INFO**: Provide requested information
- **APPROVE**: Approve the verification
- **REJECT**: Reject the verification
- **COMPLETE**: Mark as complete
- **EXPIRE**: Mark as expired
- **REVOKE**: Revoke the verification
- **ESCALATE**: Escalate to higher authority
- **REASSIGN**: Reassign to another reviewer

## Business Rules

The workflow enforces several business rules:

1. **Biometric Requirement**: High and very high level verifications require biometric evidence
2. **Evidence Count**: Minimum evidence requirements based on verification level
3. **Reviewer Authority**: Reviewers cannot approve their own submissions
4. **Approval Chain**: All required approvals must be completed
5. **Expiration**: Workflows expire after 30 days of inactivity

## Workflow Types

### Identity Verification
- Document Collection
- Initial Review
- Verification
- Final Approval

### Medical Record Verification
- Medical Document Submission
- Medical Professional Review
- Cross-Reference Check

## Notifications

The workflow system automatically sends notifications for:
- New verification submissions
- Additional information requests
- Approval/rejection decisions
- Workflow state changes