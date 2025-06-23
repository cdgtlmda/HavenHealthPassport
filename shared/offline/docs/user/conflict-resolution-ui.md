# Conflict Resolution UI Guide

## Overview

This guide explains how to use the conflict resolution interface in Haven Health Passport when data conflicts occur during synchronization. Conflicts happen when the same record is modified on multiple devices while offline.

## Understanding Conflicts

### What is a Data Conflict?

A data conflict occurs when:
- The same record is edited on two different devices
- Changes are made while offline
- Both devices try to sync their changes

### Types of Conflicts

1. **Update Conflicts** - Same field changed differently on multiple devices
2. **Delete Conflicts** - Record deleted on one device but updated on another
3. **Relationship Conflicts** - Related records have incompatible changes

## Conflict Resolution Interface

### Conflict Notification

When conflicts are detected, you'll see:

#### Mobile App
- Red badge on sync icon
- Notification banner at top of screen
- "Resolve Conflicts" button appears

#### Web Portal
- Alert icon in header
- Yellow warning bar
- Conflict count displayed

### Accessing Conflict Resolution

#### Mobile App
1. Tap the sync icon with red badge
2. Select "Resolve Conflicts"
3. Or go to Settings → Sync → Conflicts

#### Web Portal
1. Click the alert icon in header
2. Select "View Conflicts"
3. Or navigate to Settings → Data Management → Conflicts

## Resolving Conflicts

### Conflict List View

The conflict list shows:
- **Record Type** (Patient, Medical Record, Document)
- **Patient Name** (if applicable)
- **Conflict Type** (Update, Delete, etc.)
- **Devices Involved**
- **Time of Conflict**
- **Severity** (Low, Medium, High)

### Conflict Detail View

When you select a conflict, you'll see:

```
┌─────────────────────────────────────┐
│  Conflict: Patient Record Update    │
├─────────────────────────────────────┤
│                                     │
│  Your Version (This Device)         │
│  Modified: Today at 2:30 PM         │
│  ┌─────────────────────────────┐   │
│  │ Name: John Smith            │   │
│  │ DOB: 01/15/1990            │   │
│  │ Blood Type: O+             │   │
│  │ Allergies: Penicillin      │   │
│  └─────────────────────────────┘   │
│                                     │
│  Server Version (Other Device)      │
│  Modified: Today at 2:45 PM         │
│  ┌─────────────────────────────┐   │
│  │ Name: John Smith            │   │
│  │ DOB: 01/15/1990            │   │
│  │ Blood Type: O+             │   │
│  │ Allergies: Penicillin,      │   │
│  │           Sulfa             │   │
│  └─────────────────────────────┘   │
│                                     │
│  Differences Highlighted            │
│  • Allergies field modified         │
│                                     │
│  [Keep Mine] [Keep Theirs] [Merge]  │
└─────────────────────────────────────┘
```

### Resolution Options

#### 1. Keep Your Version
- Preserves changes from current device
- Overwrites other device's changes
- Use when you're confident your data is correct

#### 2. Keep Their Version
- Accepts changes from other device
- Discards your local changes
- Use when other device has more recent/accurate data

#### 3. Merge Changes
- Available for compatible changes
- Combines data from both versions
- System suggests intelligent merge

#### 4. Manual Edit
- Edit the final version manually
- Choose specific fields from each version
- Add additional changes if needed

### Auto-Resolution

Some conflicts can be resolved automatically:
- Timestamp updates (newest wins)
- Addition-only changes (both additions kept)
- Non-conflicting field updates

Settings for auto-resolution:
1. Go to Settings → Sync → Auto-Resolution
2. Enable/disable auto-resolution
3. Set preferences for different conflict types

## Conflict Resolution Workflow

### Step-by-Step Process

1. **Review Conflict Summary**
   - Understand what changed
   - Check modification times
   - Identify critical fields

2. **Compare Versions**
   - Look for highlighted differences
   - Check data accuracy
   - Consider data source reliability

3. **Choose Resolution Strategy**
   - Quick resolution for simple conflicts
   - Careful review for medical data
   - Consult team members if needed

4. **Confirm Resolution**
   - Review final version
   - Check for data integrity
   - Confirm your choice

5. **Sync Resolution**
   - Changes sync to all devices
   - Conflict marked as resolved
   - Audit trail created

### Best Practices

1. **Resolve Conflicts Promptly**
   - Don't let conflicts accumulate
   - Address high-priority conflicts first
   - Set aside time for regular review

2. **Understand the Context**
   - Check who made changes
   - Consider timing of changes
   - Verify with original source if needed

3. **Priority Guidelines**
   - Medical data: Favor most complete/recent
   - Contact info: Merge when possible
   - Documents: Keep both versions if unsure

4. **Team Coordination**
   - Communicate about shared records
   - Establish data entry protocols
   - Designate primary data entry person

## Special Cases

### Medical Record Conflicts

**High Priority Fields:**
- Medications
- Allergies
- Diagnoses
- Blood type

**Resolution Strategy:**
- Never auto-resolve
- Always review carefully
- Consult medical staff if uncertain
- Err on side of caution (keep both)

### Document Conflicts

When documents conflict:
1. Both versions are preserved
2. You choose primary version
3. Other version saved as "Alternate"
4. Can switch primary version later

### Delete Conflicts

When record deleted on one device:
- System shows what was deleted
- You can restore or confirm deletion
- Deletion reasons displayed if provided

## Conflict Prevention

### Best Practices

1. **Sync Frequently**
   - Sync when online
   - Before going offline
   - After major changes

2. **Coordinate Edits**
   - Assign record ownership
   - Communicate changes
   - Use notes/comments

3. **Offline Planning**
   - Limit edits while offline
   - Focus on new records
   - Avoid editing shared records

### Settings to Reduce Conflicts

1. **Enable Quick Sync**
   - Settings → Sync → Quick Sync
   - Syncs every 5 minutes when online

2. **Conflict Warnings**
   - Settings → Sync → Warnings
   - Alerts before editing recently synced records

3. **Read-Only Mode**
   - Settings → Sync → Read-Only
   - Prevents edits on shared records

## Troubleshooting

### Common Issues

**Conflicts Keep Reappearing**
- Check all devices are syncing
- Ensure consistent time zones
- Verify network connectivity

**Can't Resolve Conflict**
- Force sync all devices
- Clear sync cache
- Contact support if persists

**Missing Resolution Options**
- Update app to latest version
- Check user permissions
- Some conflicts require admin

### Getting Help

If you need assistance:
1. Note conflict ID (shown in details)
2. Screenshot conflict screen
3. Contact support with details
4. Provide device information

## Advanced Features

### Bulk Resolution

For multiple similar conflicts:
1. Select multiple conflicts
2. Choose bulk action
3. Apply same resolution to all
4. Review and confirm

### Resolution History

View past resolutions:
1. Settings → Sync → History
2. Filter by date/type
3. See who resolved what
4. Undo if needed (admin only)

### Custom Resolution Rules

Administrators can set rules:
- Auto-resolve by field type
- Priority by user role
- Time-based preferences
- Device hierarchy

## Summary

Remember:
- Conflicts are normal in offline use
- Take time to resolve carefully
- Medical data requires extra attention
- Prevention is better than resolution
- Sync frequently when online

The conflict resolution interface is designed to make this process as smooth as possible while ensuring data integrity and accuracy.