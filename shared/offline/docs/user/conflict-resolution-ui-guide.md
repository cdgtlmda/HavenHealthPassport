# Conflict Resolution UI Guide

## Understanding Conflicts

Conflicts happen when the same health record is edited in different places before syncing. Haven Health Passport makes resolving these conflicts simple and safe. This guide shows you how to handle conflicts when they occur.

## When Do Conflicts Happen?

Conflicts can occur when:
- 👥 You and your healthcare provider edit the same record
- 📱 You use multiple devices and edit while offline
- 👨‍⚕️ Multiple providers update your record simultaneously
- ⏰ Old changes sync after newer updates

**Important:** Conflicts are normal and your data is always safe. Both versions are preserved until you decide.

## Conflict Notification

### How You'll Know

When a conflict occurs, you'll see:

1. **Status Bar Alert**
   ```
   ⚠️ 2 records need your review
   ```

2. **Record Indicator**
   - Orange warning icon on the record
   - "Conflict" label
   - Both versions available

3. **Notification**
   - Push notification (if enabled)
   - In-app banner
   - Email alert (optional)

## Resolving Conflicts Step-by-Step

### Step 1: Open Conflict Review

When you see a conflict indicator:

1. **Tap the notification** or
2. **Go to the record** with ⚠️ icon or
3. **Open Settings → Sync → Resolve Conflicts**

### Step 2: Review Both Versions

You'll see a split-screen comparison:

```
┌─────────────────────────────────┐
│      Conflict Resolution        │
├─────────────────────────────────┤
│                                 │
│  Your Version    │ Their Version│
│  (Device)        │   (Cloud)    │
│                  │              │
│  Modified:       │  Modified:   │
│  Today 2:30 PM   │  Today 1:15 PM│
│                  │              │
│  Changes:        │  Changes:    │
│  • Medication    │  • Dosage    │
│  • Notes         │  • Schedule  │
│                  │              │
└─────────────────────────────────┘
```

### Step 3: Compare Differences

The UI highlights differences:
- 🟢 **Green** - Added information
- 🔴 **Red** - Removed information  
- 🟡 **Yellow** - Changed information
- ⚪ **Gray** - Unchanged sections

**Example comparison:**
```
Blood Pressure Reading
Your Version:          Their Version:
120/80 mmHg           130/85 mmHg
Taken at home         Taken at clinic
Note: "Feeling good"  Note: "Slightly elevated"
```

### Step 4: Choose Resolution Method

You have four options:

#### Option 1: Keep Your Version
```
[✓] Keep My Version
    Use the changes from your device
```
- Keeps all your edits
- Discards their changes
- Use when you're certain your info is correct

#### Option 2: Keep Their Version  
```
[✓] Keep Their Version
    Use the changes from the cloud
```
- Accepts their updates
- Discards your changes
- Use for provider updates you trust

#### Option 3: Merge Both (Recommended)
```
[✓] Merge Both Versions
    Combine information from both
```
- Keeps valuable info from both
- You select what to include
- Best for complementary updates

#### Option 4: Review Later
```
[✓] Decide Later
    Keep conflict for later review
```
- Postpones decision
- Both versions remain
- Reminder in 24 hours

### Step 5: Merge Process (If Selected)

If you choose "Merge Both":

1. **Field-by-field review:**
   ```
   Medication Name:
   ○ Your Version: Aspirin 81mg
   ● Their Version: Aspirin 81mg
   ✓ Same in both - automatically kept
   
   Dosage Instructions:
   ● Your Version: Once daily with food
   ○ Their Version: Once daily
   [Select which to keep or edit]
   
   Notes:
   □ Include your notes
   □ Include their notes
   ☑ Include both
   ```

2. **Custom editing:**
   - Tap any field to edit
   - Combine information manually
   - Add clarifying notes

3. **Preview merged result:**
   ```
   Preview Merged Record:
   - Medication: Aspirin 81mg
   - Instructions: Once daily with food
   - Notes: Patient reports no side effects.
            Provider notes: Continue current dose.
   ```

### Step 6: Confirm Resolution

Before saving:
1. Review your choice
2. Add resolution note (optional)
3. Tap "Resolve Conflict"
4. Confirmation appears: "✓ Conflict Resolved"

## Conflict Types and Examples

### 1. Simple Field Conflicts

**Scenario:** Different blood pressure readings

```
Your Version: 120/80 (home)
Their Version: 130/85 (clinic)

Resolution: Keep both with context
Result: "120/80 (home), 130/85 (clinic)"
```

### 2. Addition Conflicts

**Scenario:** Both added different medications

```
Your Version: + Vitamin D
Their Version: + Iron supplement

Resolution: Merge both
Result: Both medications added
```

### 3. Deletion Conflicts

**Scenario:** You deleted, they updated

```
Your Version: Medication deleted
Their Version: Dosage changed

Resolution: Review reason for deletion
Result: Keep deletion or restore with new dosage
```

### 4. Complex Conflicts

**Scenario:** Multiple fields changed

```
Your Version: 
- Condition improved
- Medication reduced
- Next appointment in 3 months

Their Version:
- Additional tests ordered  
- Medication unchanged
- Next appointment in 1 month

Resolution: Merge carefully
Result: Keep provider's clinical decisions,
        add your symptom improvements
```

## Visual Interface Elements

### Conflict List View

When you have multiple conflicts:

```
┌─────────────────────────────────┐
│  Conflicts to Resolve (3)       │
├─────────────────────────────────┤
│                                 │
│ ⚠️ Blood Pressure Reading       │
│    Modified by: Dr. Smith       │
│    2 hours ago                  │
│    [Review] →                   │
│                                 │
│ ⚠️ Medication: Metformin        │
│    Modified by: You             │
│    Yesterday                    │
│    [Review] →                   │
│                                 │
│ ⚠️ Allergy List                 │
│    Modified by: Nurse Johnson   │
│    3 days ago                   │
│    [Review] →                   │
│                                 │
└─────────────────────────────────┘
```

### Detailed Comparison View

The comparison screen shows:

1. **Header Information**
   - Record type and title
   - Who made changes
   - When changes were made
   - Sync status

2. **Visual Diff Display**
   - Side-by-side comparison
   - Color-coded changes
   - Expandable sections
   - Zoom for images

3. **Action Buttons**
   - Keep Mine
   - Keep Theirs  
   - Merge Both
   - More Options

### Merge Interface

The merge screen provides:

```
┌─────────────────────────────────┐
│       Merge Records             │
├─────────────────────────────────┤
│                                 │
│ Select information to keep:     │
│                                 │
│ Blood Pressure:                 │
│ ☑ 120/80 (your reading)        │
│ ☑ 130/85 (clinic reading)      │
│                                 │
│ Notes:                          │
│ ☑ "Taken after exercise"       │
│ ☑ "Patient appears stressed"   │
│                                 │
│ [Custom Note Field]             │
│ _____________________________   │
│                                 │
│ [Preview] [Cancel] [Save]       │
└─────────────────────────────────┘
```

## Best Practices for Users

### For Patients

**Do:**
- ✅ Review conflicts promptly
- ✅ Keep provider updates for clinical data
- ✅ Merge when both have valuable info
- ✅ Add notes explaining your choice
- ✅ Ask providers if unsure

**Don't:**
- ❌ Ignore conflicts indefinitely
- ❌ Always choose your version
- ❌ Delete provider updates without reading
- ❌ Resolve without understanding changes

### For Healthcare Providers

**Clinical conflicts:**
- Always review patient-reported symptoms
- Merge observations from different visits
- Document reason for overriding patient data
- Communicate changes to patient

**Best practices:**
- Review conflicts before appointments
- Explain changes to patients
- Use merge for comprehensive records
- Add clinical notes for clarity

### For NGO Workers

**Field operations:**
- Process conflicts during sync windows
- Train beneficiaries on conflict resolution
- Use bulk resolution when appropriate
- Document resolution patterns

**Common scenarios:**
- Multiple registration points
- Different providers updating
- Beneficiary self-reports
- Translation differences

## Conflict Prevention Tips

### Reduce Conflicts By:

1. **Regular Syncing**
   - Sync at least daily
   - Sync before and after edits
   - Use auto-sync when online

2. **Communication**
   - Inform providers of updates
   - Check before major edits
   - Coordinate care team changes

3. **Clear Ownership**
   - Let providers update clinical data
   - Patients update personal info
   - Designate primary updater

4. **Timely Updates**
   - Enter data promptly
   - Don't delay syncing
   - Review pending changes

## Advanced Features

### Bulk Conflict Resolution

For multiple similar conflicts:

1. **Select Multiple**
   - Long press first conflict
   - Tap others to select
   - Choose bulk action

2. **Bulk Actions**
   - Keep all mine
   - Keep all theirs
   - Review individually
   - Apply rule

### Conflict History

View past resolutions:

```
Settings → Sync → Conflict History

Shows:
- Resolved conflicts
- Resolution method
- Who resolved
- When resolved
- Ability to undo
```

### Smart Resolution

AI-assisted suggestions:

- Detects duplicate entries
- Suggests obvious merges
- Flags critical conflicts
- Learns from your patterns

## Accessibility Features

### For Visual Impairments

- **High contrast mode** for comparisons
- **Screen reader** compatible
- **Audio descriptions** of changes
- **Large text** options

### For Limited Literacy

- **Icon-based** indicators
- **Color coding** for changes
- **Simple language** mode
- **Voice guidance** available

### For Motor Impairments

- **Large tap targets**
- **Gesture alternatives**
- **Voice commands**
- **Adjustable timeouts**

## Getting Help

### In-App Assistance

1. **Help Button** on conflict screen
2. **Video tutorial** for first conflict
3. **Practice mode** with examples
4. **Live chat** when online

### Common Questions

**"Which version should I keep?"**
- Keep provider versions for medical data
- Keep your versions for personal notes
- Merge when both have value

**"What if I choose wrong?"**
- Conflict history saves both versions
- Can undo within 30 days
- Contact support for help

**"Can conflicts harm my records?"**
- No, both versions are preserved
- You can always recover
- System prevents data loss

## Summary

Conflict resolution ensures your health records remain accurate when updates come from multiple sources. The interface is designed to be:

- **Safe** - No data loss
- **Simple** - Easy choices
- **Smart** - Helpful suggestions
- **Flexible** - Multiple options

Remember: When in doubt, merge both versions or ask for help. Your health data is too important to guess.

---

*For more help, see [Sync Status Guide](./sync-status-explanations.md) or contact support.*