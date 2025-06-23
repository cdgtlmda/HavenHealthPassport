# Troubleshooting FAQs

## Frequently Asked Questions and Solutions

This guide provides answers to common questions and solutions to frequent issues with Haven Health Passport's offline functionality.

## Quick Links

- [Connection Issues](#connection-issues)
- [Sync Problems](#sync-problems)
- [Storage Issues](#storage-issues)
- [Login & Access](#login--access)
- [Data & Records](#data--records)
- [App Performance](#app-performance)
- [Sharing & Privacy](#sharing--privacy)
- [Technical Issues](#technical-issues)

## Connection Issues

### Q: The app says I'm offline but I have internet. What should I do?

**A:** Try these steps:
1. Check your device's internet connection in settings
2. Turn airplane mode on, wait 10 seconds, turn it off
3. Force close and restart the app
4. Check if other apps can access internet
5. Reset network settings if problem persists

**For mobile:**
- iOS: Settings → General → Reset → Reset Network Settings
- Android: Settings → System → Reset → Reset Network Settings

### Q: Why won't the app connect to WiFi?

**A:** Common causes and solutions:
- **Weak signal**: Move closer to router
- **Login required**: Open browser, complete WiFi login
- **Firewall blocking**: Check with IT administrator
- **VPN interference**: Temporarily disable VPN
- **DNS issues**: Change DNS to 8.8.8.8 or 1.1.1.1

### Q: Can I use the app with limited internet?

**A:** Yes! The app works well with:
- 2G/3G connections (sync will be slower)
- Intermittent connections (resumes when reconnected)
- Data-saving mode (compress images)
- Metered connections (WiFi-only sync option)

## Sync Problems

### Q: My data isn't syncing. What's wrong?

**A:** Check these common issues:

1. **Sync Status Icon**
   - 🟡 Yellow = Changes pending (normal offline)
   - 🔴 Red = Error (action needed)
   - ⚠️ Orange = Conflict (review needed)

2. **Common Fixes:**
   ```
   1. Pull down to refresh
   2. Go to Settings → Sync → Sync Now
   3. Check internet connection
   4. Sign out and back in
   5. Clear app cache
   ```

3. **Still Not Working?**
   - Check sync queue (Settings → Sync → Queue)
   - Look for error messages
   - Try selective sync
   - Contact support with error details

### Q: How do I resolve sync conflicts?

**A:** Follow these steps:
1. Tap the conflict notification ⚠️
2. Review both versions side-by-side
3. Choose:
   - Keep your version
   - Keep their version
   - Merge both (recommended)
   - Decide later
4. Add a note explaining your choice
5. Tap "Resolve"

**Tips:**
- Provider updates usually have clinical data
- Your updates have personal notes
- When unsure, merge both
- You can undo within 30 days

### Q: Why is sync taking so long?

**A:** Sync can be slow due to:
- **Large photos/documents**: Use WiFi for faster sync
- **Many changes**: First sync after long offline period
- **Poor connection**: Wait for better signal
- **Server busy**: Try during off-peak hours

**Speed up sync:**
- Connect to WiFi
- Close other apps
- Keep screen on
- Sync overnight
- Reduce photo quality in settings

## Storage Issues

### Q: I'm getting "Storage Full" errors. Help!

**A:** Free up space:

1. **Quick Fixes:**
   - Clear cache: Settings → Storage → Clear Cache
   - Delete old photos: Records → Photos → Select → Delete
   - Remove duplicates: Settings → Cleanup → Find Duplicates

2. **More Space:**
   - Archive old records (moves to cloud)
   - Reduce offline years (Settings → Offline Data)
   - Compress images (Settings → Storage → Compress)
   - Delete unused documents

3. **Prevent Future Issues:**
   - Enable auto-cleanup
   - Set photo quality to medium
   - Regularly review storage
   - Use cloud-only for old data

### Q: How much storage does the app need?

**A:** Storage requirements:
- **Minimum**: 500MB free space
- **Recommended**: 2GB free space
- **Typical usage**: 1-3GB
- **Heavy usage**: 3-5GB (many photos)

**Storage breakdown:**
- App: 200MB
- Text records: 100-500MB
- Photos: 500MB-3GB
- Documents: 200MB-1GB

### Q: Can I move the app to SD card?

**A:** 
- **Android**: Yes, if your device supports it
  - Settings → Apps → Haven Health → Storage → Change
- **iOS**: No, iOS doesn't support SD cards
- **Note**: May affect performance and offline features

## Login & Access

### Q: I can't log in while offline. Why?

**A:** Offline login requirements:
1. You must have logged in online at least once
2. Offline access must be enabled
3. It's been less than 30 days since last online login
4. Your credentials are cached

**Fix offline login:**
1. Connect to internet
2. Log in normally
3. Go to Settings → Offline Access
4. Enable "Remember me for offline"
5. Test by going offline and restarting app

### Q: I forgot my password and I'm offline. What can I do?

**A:** Options:
1. **If you have biometric login**: Use fingerprint/face
2. **If you have PIN**: Use PIN instead
3. **Emergency access**: Use emergency access code
4. **Must reset**: Need internet to reset password

**Prevent future issues:**
- Set up biometric login
- Create offline PIN
- Save emergency access code
- Use password manager

### Q: The app keeps logging me out. How do I fix this?

**A:** Common causes:
- **Security timeout**: Extend in Settings → Security
- **Multiple devices**: Check if logged in elsewhere
- **App updates**: Re-enable "stay logged in"
- **iOS/Android settings**: Check battery optimization

**Solutions:**
```
Settings → Security
☑ Keep me logged in
☑ Remember for offline
Auto-logout: Never (or choose time)
☑ Use biometric login
```

## Data & Records

### Q: Some of my records are missing. Where are they?

**A:** Check these locations:
1. **Filters active**: Clear all filters
2. **Archive**: Check archived records
3. **Cloud-only**: Look for ☁️ symbol
4. **Other device**: May be on different device
5. **Sync pending**: Pull down to refresh

**Recovery steps:**
1. Go to Records → All
2. Remove any filters
3. Search by keyword
4. Check Archive folder
5. Sync when online
6. Restore from backup if needed

### Q: I accidentally deleted important records. Can I recover them?

**A:** Yes! Deleted records can be recovered:
1. **Within 30 days**:
   - Go to Settings → Data → Trash
   - Find deleted records
   - Tap "Restore"

2. **After 30 days**:
   - Contact support
   - Provide record details
   - May recover from backup

3. **Prevent accidents**:
   - Enable deletion confirmation
   - Regular backups
   - Star important records

### Q: My photos aren't loading. What's wrong?

**A:** Photo loading issues:

**If offline:**
- Only compressed versions available offline
- Large photos may be cloud-only
- Check Settings → Offline Data → Include Photos

**If online:**
- Slow connection (wait or use WiFi)
- Corrupted cache (clear cache)
- Storage full (free up space)

**Fix steps:**
1. Check storage space
2. Clear image cache
3. Re-download photos
4. Check photo settings
5. Restart app

## App Performance

### Q: The app is running slowly. How can I speed it up?

**A:** Performance optimization:

1. **Quick Fixes:**
   ```
   - Close other apps
   - Restart your device
   - Clear app cache
   - Free up storage (need 20% free)
   - Update to latest version
   ```

2. **Settings Adjustments:**
   ```
   Settings → Performance
   ☑ Reduce animations
   ☑ Limit background sync
   ☐ High quality images (uncheck)
   ☑ Compress old data
   ```

3. **Data Management:**
   - Archive old records
   - Delete unused photos
   - Limit offline years to 2
   - Use search instead of scrolling

### Q: The app crashes or freezes. What should I do?

**A:** Troubleshooting steps:

1. **Immediate fixes:**
   - Force close app
   - Restart device
   - Check for updates
   - Clear cache

2. **If crashes persist:**
   - Note what you were doing
   - Check crash logs (Settings → About → Logs)
   - Reinstall app (backup first!)
   - Contact support with details

3. **Prevent crashes:**
   - Keep app updated
   - Maintain free storage
   - Don't interrupt sync
   - Regular device restarts

### Q: Battery drains quickly when using the app. Why?

**A:** Battery optimization:

**High drain causes:**
- Continuous sync
- GPS/Location services
- Screen brightness
- Background refresh
- Large file uploads

**Solutions:**
```
Settings → Battery
☑ Battery saver mode
☐ Background sync (when low)
Sync interval: Every 2 hours
☑ WiFi sync only
☐ Auto-download images
```

## Sharing & Privacy

### Q: I can't share records with my provider. Help!

**A:** Sharing troubleshooting:

1. **Check basics:**
   - Internet connection (for link sharing)
   - Provider in your contacts
   - Sharing permissions enabled
   - Records not in private mode

2. **Try different methods:**
   - QR code (works offline)
   - PDF export
   - Secure link (needs internet)
   - Direct provider access

3. **Common fixes:**
   - Update provider email
   - Regenerate sharing link
   - Check spam folder
   - Use QR for in-person

### Q: How do I stop sharing with someone?

**A:** Revoke access:

1. Go to Settings → Privacy → Active Shares
2. Find the person/provider
3. Tap "Revoke Access"
4. Confirm action
5. They lose access immediately

**Or set expiration:**
- When sharing, set time limit
- Auto-expires after set period
- No manual revocation needed

### Q: Is my data really private and secure?

**A:** Yes! Security measures:

**Protection layers:**
- 🔐 End-to-end encryption
- 🔑 Your keys only
- 📱 Device encryption
- 🌐 Secure transmission
- 🏥 HIPAA compliant

**You control:**
- Who sees what
- How long they access
- What they can do
- Complete audit trail
- Right to delete

## Technical Issues

### Q: The app won't install or update. What's wrong?

**A:** Installation issues:

**Common problems:**
- Insufficient storage (need 500MB)
- Old OS version (update device)
- Regional restrictions (use VPN)
- Corrupted download (retry)

**Solutions by platform:**

**iOS:**
1. Check iOS version (need 12+)
2. Sign out of App Store, sign back in
3. Reset network settings
4. Delete and reinstall

**Android:**
1. Check Android version (need 8+)
2. Clear Play Store cache
3. Check date/time settings
4. Enable "Unknown sources" if needed

### Q: I get error messages I don't understand. What do they mean?

**A:** Common error codes:

| Error | Meaning | Solution |
|-------|---------|----------|
| E001 | Network timeout | Check connection, retry |
| E002 | Auth failed | Login again |
| E003 | Storage full | Free up space |
| E004 | Sync conflict | Resolve conflicts |
| E005 | Version mismatch | Update app |
| E006 | Server error | Wait and retry |
| E007 | Invalid data | Check input, retry |
| E008 | Permission denied | Check settings |

### Q: The QR code scanner isn't working. How do I fix it?

**A:** QR scanner fixes:

1. **Check permissions:**
   - Settings → App Permissions → Camera → Allow

2. **Common issues:**
   - Poor lighting (need good light)
   - Dirty camera lens (clean it)
   - QR code damaged (request new one)
   - Wrong QR type (must be Haven Health)

3. **Alternatives:**
   - Type code manually
   - Use sharing link
   - Export as PDF
   - Try different device

## Getting Additional Help

### Q: I tried everything but still have problems. What now?

**A:** Get support:

1. **Self-Help Resources:**
   - In-app help (? icon)
   - Video tutorials
   - User manual
   - Community forum

2. **Direct Support:**
   - **Chat**: In app when online
   - **Email**: support@havenhealthpassport.org
   - **Phone**: +1-XXX-XXX-XXXX
   - **Hours**: Mon-Fri 9AM-5PM EST

3. **Information to Provide:**
   - Device model and OS version
   - App version
   - Error messages/screenshots
   - Steps to reproduce
   - When problem started

### Q: Is there a user community I can join?

**A:** Yes! Community resources:

- **Forum**: community.havenhealthpassport.org
- **Facebook**: Haven Health Users
- **Local groups**: Check with NGOs
- **Video tutorials**: YouTube channel
- **Newsletter**: Monthly tips and updates

### Q: How do I report a bug or suggest a feature?

**A:** We welcome feedback:

1. **In-app feedback:**
   - Settings → Help → Send Feedback
   - Include screenshots
   - Describe issue clearly

2. **Feature requests:**
   - Email: features@havenhealthpassport.org
   - Forum: Feature Request section
   - Vote on existing requests

3. **Bug reports:**
   - Use in-app tool for logs
   - Include reproduction steps
   - Note frequency of issue

## Quick Reference Card

### Essential Fixes

**No Internet? Try:**
- Airplane mode on/off
- Restart device
- Reset network settings
- Check WiFi password

**Sync Issues? Try:**
- Pull down to refresh
- Manual sync in settings
- Check sync queue
- Clear cache

**Storage Full? Try:**
- Delete old photos
- Clear cache
- Archive old records
- Compress images

**Can't Login? Try:**
- Use biometric
- Check offline setting
- Reset password (online)
- Contact support

**Slow Performance? Try:**
- Close other apps
- Free up storage
- Reduce offline data
- Update app

Remember: Most issues have simple solutions. When in doubt, restart the app, check your connection, and ensure you have the latest version.

---

*Updated: [Current Date]*  
*Version: 1.0*  
*For more help: [User Guide](./offline-feature-guide.md) | [Support](mailto:support@havenhealthpassport.org)*