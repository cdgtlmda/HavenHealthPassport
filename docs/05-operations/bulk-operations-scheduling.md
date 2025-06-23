# Bulk Operations Scheduling Implementation

## Overview

This document describes the implementation of scheduling functionality for bulk operations in the Haven Health Passport system. The implementation allows users to schedule import, export, and update operations for future execution.

## Features Implemented

### 1. Scheduling Infrastructure

- **Database Model**: Created `BulkOperation` model to track scheduled operations
- **Celery Integration**: Set up Celery with Redis for background task execution
- **API Endpoints**: Added scheduling endpoints for import, export, and update operations

### 2. Frontend Implementation

All three bulk operation types (Import, Export, Update) have scheduling UI:
- Date/time picker for selecting execution time
- Email notification toggle
- Visual feedback for scheduled operations

### 3. Backend Endpoints

#### Schedule Import
```
POST /api/v2/bulk/import/schedule
```
- Accepts CSV data and scheduling parameters
- Creates background task for future execution
- Sends confirmation email

#### Schedule Export  
```
POST /api/v2/bulk/export/schedule
```
- Accepts export format and field selection
- Schedules export generation
- Sends email with download link when complete

#### Schedule Update
```
POST /api/v2/bulk/update/schedule
```
- Accepts patient IDs and update parameters
- Creates backup before execution
- Sends completion notification

### 4. Rollback Functionality

#### Import Rollback
```
POST /api/v2/bulk/import/rollback/{import_id}
```
- Allows rollback within 24 hours
- Deletes imported records
- Updates audit logs

#### Update Rollback
```
POST /api/v2/bulk/update/rollback/{update_id}
```
- Restores from automatic backup
- Maintains data integrity
- Tracks rollback in audit trail

### 5. Notification System

- Real-time WebSocket notifications
- Email notifications for scheduled operations
- In-app notification preferences
- Operation status tracking

## Database Schema

```sql
CREATE TABLE bulk_operations (
    id VARCHAR(255) PRIMARY KEY,
    type ENUM('import', 'export', 'update', 'delete'),
    status ENUM('scheduled', 'processing', 'completed', 'failed', 'cancelled'),
    user_id VARCHAR(255) NOT NULL,
    organization_id VARCHAR(255) NOT NULL,
    scheduled_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parameters TEXT, -- JSON
    result TEXT, -- JSON
    error_message TEXT
);
```

## Celery Configuration

The system uses Celery with Redis for task scheduling:
- Separate queue for bulk operations
- Automatic retry on failure
- Task result persistence
- Periodic cleanup of old operations

## Security Considerations

- All operations require authentication
- Permission checks for each operation type
- Organization-level data isolation
- Audit logging for all operations
- Secure parameter storage

## Future Enhancements

1. **Recurring Schedules**: Allow operations to repeat on a schedule
2. **Dependency Management**: Chain operations together
3. **Advanced Notifications**: SMS and webhook support
4. **Performance Monitoring**: Track operation performance metrics
5. **Resource Management**: Prevent system overload from concurrent operations

## Testing

To test the scheduling functionality:

1. Start Redis server: `redis-server`
2. Start Celery worker: `celery -A src.celery_app worker --loglevel=info`
3. Start Celery beat: `celery -A src.celery_app beat --loglevel=info`
4. Run the application and test scheduling through the UI

## Monitoring

- Check scheduled operations: `/api/v2/bulk-operations/scheduled`
- View operation status: `/api/v2/bulk-operations/{operation_id}/status`
- Cancel scheduled operation: `/api/v2/bulk-operations/{operation_id}/cancel`
