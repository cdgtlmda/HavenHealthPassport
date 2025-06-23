# Understanding Sync Status

## What is Sync?

Sync (synchronization) is the process of keeping your health records up-to-date across all your devices and with your healthcare providers. This guide explains what each sync status means and what actions you might need to take.

## Sync Status Indicators

### Visual Indicators

Haven Health Passport uses simple visual indicators to show sync status:

| Icon | Color | Status | Meaning |
|------|-------|--------|---------|
| ✓ | Green | Synced | All data is up-to-date |
| ⏳ | Yellow | Pending | Changes waiting to sync |
| 🔄 | Blue | Syncing | Currently synchronizing |
| ⚠️ | Orange | Conflict | Manual review needed |
| ❌ | Red | Error | Sync failed, action required |
| ☁️ | Gray | Cloud-Only | Not downloaded for offline |
| 📵 | Gray | Offline | No internet connection |

## Detailed Status Explanations

### ✓ Synced (Green)

**What it means:**
- Your data is fully synchronized
- All changes have been uploaded
- You have the latest updates
- No action needed

**When you'll see this:**
- After successful sync
- When viewing unchanged records
- When online with no pending changes

### ⏳ Pending (Yellow)

**What it means:**
- You've made changes offline
- Changes are saved locally
- Waiting for internet to sync
- Your data is safe

**Common scenarios:**
- Added records while offline
- Edited information without internet
- Uploaded photos in airplane mode
- Updated emergency contacts offline

**What to do:**
- Nothing required - will sync automatically
- To sync now: connect to internet
- Your changes are safely stored

### 🔄 Syncing (Blue)

**What it means:**
- Actively exchanging data
- Uploading your changes
- Downloading updates
- Process in progress

**What you'll see:**
- Progress bar showing completion
- Number of items syncing
- Estimated time remaining
- Data transfer indicators

**What to do:**
- Keep the app open if possible
- Stay connected to internet
- Don't close the app
- Be patient with large files

### ⚠️ Conflict (Orange)

**What it means:**
- Same record edited in multiple places
- System needs your decision
- Both versions are preserved
- Manual review required

**Why conflicts happen:**
- You and provider edited same record
- Multiple devices used
- Offline edits on different devices
- Simultaneous updates

**What to do:**
1. Tap the conflict notification
2. Review both versions
3. Choose the correct version
4. Or merge information from both
5. Confirm your choice

**Detailed conflict resolution:**
See our [Conflict Resolution Guide](./conflict-resolution-ui-guide.md)

### ❌ Error (Red)

**What it means:**
- Sync failed to complete
- Problem needs attention
- Data not synchronized
- Action required

**Common causes:**
- Network timeout
- Authentication expired
- Server temporarily unavailable
- Storage full
- App needs update

**What to do:**
1. Check internet connection
2. Try manual sync
3. Restart the app
4. Check for app updates
5. Contact support if persists

### ☁️ Cloud-Only (Gray Cloud)

**What it means:**
- Record exists in cloud
- Not downloaded to device
- Requires internet to view
- Saves device storage

**When you'll see this:**
- Older records not accessed recently
- Large files (X-rays, scans)
- Archived documents
- Records from other devices

**What to do:**
- Tap to download for offline access
- Connect to WiFi for large files
- Manage offline storage in settings

### 📵 Offline (Gray)

**What it means:**
- No internet connection
- Working in offline mode
- All changes saved locally
- Will sync when online

**What you can do offline:**
- View downloaded records
- Add new information
- Edit existing data
- Take photos
- Export records

**What requires internet:**
- Downloading new records
- Receiving provider updates
- Blockchain verification
- Real-time translation

## Sync Details by Feature

### Health Records Sync

**Individual record states:**
- Each record has its own sync status
- Recently accessed records sync first
- Older records may be cloud-only
- Photos sync separately from text

**Priority syncing:**
1. Emergency information (always synced)
2. Current medications
3. Recent medical visits
4. Test results
5. Historical records

### Document Sync

**Document sync behavior:**
- Text syncs immediately
- Photos compressed and queued
- Large files sync on WiFi only
- PDFs may take longer

**Storage optimization:**
- Recent documents kept offline
- Older documents in cloud
- Thumbnails sync first
- Full quality on demand

### Provider Updates

**Receiving updates:**
- 🔔 Notification when updates arrive
- Auto-download on WiFi
- Summary shows what's new
- Review changes before accepting

**Update types:**
- New test results
- Prescription changes
- Appointment summaries
- Provider notes

## Understanding Sync Progress

### Sync Progress Bar

When syncing, you'll see:

```
Syncing... 45%
↑ 12 items | ↓ 8 items
Time remaining: ~2 minutes
```

**What the numbers mean:**
- **Percentage**: Overall completion
- **↑ Upload**: Your changes going up
- **↓ Download**: Updates coming down
- **Time**: Estimated completion

### Sync Stages

1. **Preparing** (0-10%)
   - Checking what needs syncing
   - Comparing versions
   - Planning sync order

2. **Uploading** (10-50%)
   - Sending your changes
   - Uploading new records
   - Transmitting photos

3. **Downloading** (50-90%)
   - Receiving updates
   - Getting new records
   - Downloading attachments

4. **Finalizing** (90-100%)
   - Verifying data integrity
   - Updating local database
   - Cleaning up temporary files

## Sync Settings

### Automatic Sync Settings

Configure how and when to sync:

**Sync Frequency:**
- Continuous (when online)
- Every 30 minutes
- Every hour
- Manual only

**Sync Conditions:**
- WiFi only
- WiFi + Cellular
- When charging
- Battery above 20%

**Data Limits:**
- No limit
- 10MB per sync
- 50MB per sync
- 100MB per sync

### Smart Sync Features

**Intelligent Syncing:**
- Recent records sync first
- Emergency info always current
- Photos sync when on WiFi
- Large files sync overnight

**Battery Optimization:**
- Reduced sync when battery low
- Pause sync in power saving mode
- Resume when charging
- Efficient data compression

## Troubleshooting Sync Issues

### Common Problems and Solutions

**"Sync stuck at X%"**
- Wait 5 minutes (large files)
- Check internet speed
- Restart sync manually
- Clear app cache

**"Cannot connect to server"**
- Verify internet connection
- Check app permissions
- Update to latest version
- Try again later

**"Authentication failed"**
- Log out and back in
- Reset password if needed
- Check account status
- Contact support

**"Storage full"**
- Delete old photos
- Clear cache
- Archive old records
- Upgrade storage plan

### Sync Best Practices

**For Best Performance:**
1. Sync regularly (daily)
2. Use WiFi when possible
3. Keep app updated
4. Don't force close during sync
5. Maintain free storage space

**Data Safety:**
- Your data is always encrypted
- Local copies kept until confirmed
- Multiple backup points
- No data loss during sync

## Sync FAQs

**Q: How often should I sync?**
A: At least once daily when you have internet. The app syncs automatically every 30 minutes when online.

**Q: Will syncing use a lot of data?**
A: Text records use minimal data (KB). Photos and documents use more (MB). Use WiFi for large syncs.

**Q: What if sync fails?**
A: Your data is safe locally. The app will retry automatically. You can also trigger manual sync.

**Q: Can I sync on slow internet?**
A: Yes, but it may take longer. The app resumes where it left off if interrupted.

**Q: Do I need to keep the app open?**
A: For best results, yes. On mobile, background sync works but may be slower.

**Q: What happens to deleted records?**
A: Deleted records sync too. They're marked as deleted but retained for 30 days for recovery.

**Q: Can I choose what to sync?**
A: Yes, in Settings → Sync Options, you can select specific record types or date ranges.

**Q: Is syncing secure?**
A: Yes, all data is encrypted during transfer and storage. Only you and authorized providers can access it.

## Getting Sync Help

### Quick Checks

Before contacting support, try:
1. ✓ Restart the app
2. ✓ Check internet connection
3. ✓ Verify login credentials
4. ✓ Update the app
5. ✓ Clear cache

### Support Options

**Self-Help:**
- In-app help center
- Video tutorials
- Community forums
- FAQ section

**Direct Support:**
- In-app chat (when online)
- Email: sync-help@havenhealthpassport.org
- Phone: +1-XXX-XXX-XXXX
- Local NGO assistance

### Reporting Sync Issues

When reporting issues, provide:
- Device type and OS version
- App version
- Sync error message
- Time of occurrence
- Internet connection type
- Screenshot if possible

## Summary

Sync keeps your health records current and accessible across all devices. Understanding sync status helps you:
- Know when data is current
- Identify issues quickly
- Take appropriate action
- Maintain data integrity

Remember: Your data is always safe locally, even if sync fails temporarily.

---

*For more help, see our [Offline Feature Guide](./offline-feature-guide.md) and [Troubleshooting Guide](./troubleshooting-faqs.md)*