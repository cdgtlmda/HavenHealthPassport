# Haven Health Passport - Quick Start Guide

## For Immediate Deployment:

1. **Configure APIs** (Required)
   ```bash
   python scripts/setup_medical_apis.py --environment production
   ```

2. **Deploy Infrastructure**
   ```bash
   python scripts/deploy_to_production.py --environment production
   ```

3. **Validate Deployment**
   ```bash
   python scripts/validate_production.py
   ```

## Current Status:
- Implementation: COMPLETE
- Backend: READY
- Generated: 2025-06-11T00:02:26.550691

## Critical Note:
This system manages healthcare data for vulnerable refugee populations.
Ensure all safety measures are in place before serving real patients.
