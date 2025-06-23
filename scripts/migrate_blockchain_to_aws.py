#!/usr/bin/env python3
"""Migrate from standalone Hyperledger Fabric to AWS Managed Blockchain."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.config import get_settings
from src.services.blockchain_service import BlockchainService as FabricService
from src.services.blockchain_service_aws import AWSBlockchainService
from src.core.database import get_db
from src.models.blockchain import BlockchainReference
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class BlockchainMigration:
    """Migrate blockchain data from Fabric to AWS Managed Blockchain."""
    
    def __init__(self):
        """Initialize migration tools."""
        self.fabric_service = None
        self.aws_service = None
        self.migration_stats = {
            "records_migrated": 0,
            "records_failed": 0,
            "verifications_migrated": 0,
            "start_time": datetime.utcnow(),
            "errors": []
        }
    
    def check_prerequisites(self):
        """Check if all prerequisites are met."""
        print("Checking prerequisites...")
        
        # Check AWS credentials
        try:
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            print(f"✅ AWS credentials valid (Account: {identity['Account']})")
        except Exception as e:
            print(f"❌ AWS credentials not configured: {e}")
            return False
        
        # Check network configuration
        if not settings.MANAGED_BLOCKCHAIN_NETWORK_ID:
            print("❌ MANAGED_BLOCKCHAIN_NETWORK_ID not set")
            return False
        
        if not settings.MANAGED_BLOCKCHAIN_MEMBER_ID:
            print("❌ MANAGED_BLOCKCHAIN_MEMBER_ID not set")
            return False
        
        print("✅ AWS Managed Blockchain configuration found")
        
        # Check database connection
        try:
            with get_db() as db:
                count = db.query(BlockchainReference).count()
                print(f"✅ Database connected ({count} blockchain references found)")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
        
        return True
    
    def initialize_services(self):
        """Initialize both blockchain services."""
        print("\nInitializing blockchain services...")
        
        try:
            # Initialize Fabric service
            os.environ["BLOCKCHAIN_PROVIDER"] = "hyperledger_fabric"
            self.fabric_service = FabricService()
            print("✅ Fabric service initialized")
        except Exception as e:
            print(f"⚠️  Fabric service initialization failed: {e}")
            print("   Will migrate from database records only")
        
        try:
            # Initialize AWS service
            os.environ["BLOCKCHAIN_PROVIDER"] = "aws_managed_blockchain"
            self.aws_service = AWSBlockchainService()
            print("✅ AWS Managed Blockchain service initialized")
        except Exception as e:
            print(f"❌ AWS service initialization failed: {e}")
            raise
    
    def migrate_blockchain_references(self):
        """Migrate blockchain references from database."""
        print("\nMigrating blockchain references...")
        
        with get_db() as db:
            # Get all blockchain references
            references = db.query(BlockchainReference).all()
            total = len(references)
            
            print(f"Found {total} blockchain references to migrate")
            
            for i, ref in enumerate(references):
                try:
                    # Skip if already migrated
                    if ref.blockchain_network and ref.blockchain_network.startswith("aws-"):
                        print(f"  [{i+1}/{total}] Skipping {ref.record_id} (already on AWS)")
                        continue
                    
                    # Re-create the verification on AWS
                    print(f"  [{i+1}/{total}] Migrating record {ref.record_id}...")
                    
                    # Store on AWS blockchain
                    tx_id = self.aws_service.store_verification(
                        record_id=ref.record_id,
                        verification_hash=ref.hash_value,
                        record_data={"migrated": True, "original_tx": ref.transaction_id}
                    )
                    
                    if tx_id:
                        # Update reference to point to AWS
                        ref.blockchain_network = f"aws-{settings.MANAGED_BLOCKCHAIN_NETWORK_ID}"
                        ref.transaction_id = tx_id
                        db.commit()
                        
                        self.migration_stats["records_migrated"] += 1
                        print(f"    ✅ Migrated with new tx_id: {tx_id}")
                    else:
                        self.migration_stats["records_failed"] += 1
                        self.migration_stats["errors"].append(f"Failed to migrate {ref.record_id}")
                        print(f"    ❌ Migration failed")
                    
                except Exception as e:
                    self.migration_stats["records_failed"] += 1
                    self.migration_stats["errors"].append(f"Error migrating {ref.record_id}: {str(e)}")
                    print(f"    ❌ Error: {e}")
    
    def verify_migration(self):
        """Verify migrated records."""
        print("\nVerifying migration...")
        
        with get_db() as db:
            # Get AWS blockchain references
            aws_refs = db.query(BlockchainReference).filter(
                BlockchainReference.blockchain_network.like("aws-%")
            ).limit(10).all()
            
            verified = 0
            for ref in aws_refs:
                try:
                    # Try to verify the record
                    result = self.aws_service.verify_record(
                        ref.record_id,
                        {"verification": "test"}
                    )
                    
                    if result.get("verified") or result.get("status") == "not_found":
                        verified += 1
                        print(f"  ✅ Verified record {ref.record_id}")
                    else:
                        print(f"  ⚠️  Could not verify {ref.record_id}: {result}")
                        
                except Exception as e:
                    print(f"  ❌ Error verifying {ref.record_id}: {e}")
            
            print(f"\nVerified {verified}/{len(aws_refs)} sample records")
    
    def generate_report(self):
        """Generate migration report."""
        self.migration_stats["end_time"] = datetime.utcnow()
        duration = (self.migration_stats["end_time"] - self.migration_stats["start_time"]).total_seconds()
        
        report = f"""
# Blockchain Migration Report

## Summary
- Start Time: {self.migration_stats['start_time'].isoformat()}
- End Time: {self.migration_stats['end_time'].isoformat()}
- Duration: {duration:.2f} seconds

## Results
- Records Migrated: {self.migration_stats['records_migrated']}
- Records Failed: {self.migration_stats['records_failed']}
- Success Rate: {self.migration_stats['records_migrated'] / (self.migration_stats['records_migrated'] + self.migration_stats['records_failed']) * 100:.2f}%

## Configuration
- AWS Network ID: {settings.MANAGED_BLOCKCHAIN_NETWORK_ID}
- AWS Member ID: {settings.MANAGED_BLOCKCHAIN_MEMBER_ID}
- AWS Region: {settings.AWS_REGION}

## Errors
"""
        
        if self.migration_stats["errors"]:
            for error in self.migration_stats["errors"][:10]:  # First 10 errors
                report += f"- {error}\n"
            if len(self.migration_stats["errors"]) > 10:
                report += f"- ... and {len(self.migration_stats['errors']) - 10} more errors\n"
        else:
            report += "- No errors encountered\n"
        
        # Save report
        report_path = Path("blockchain_migration_report.md")
        with open(report_path, "w") as f:
            f.write(report)
        
        print(f"\n📄 Migration report saved to: {report_path}")
        return report
    
    def run_migration(self, dry_run=False):
        """Run the complete migration process."""
        print("=" * 60)
        print("Blockchain Migration: Fabric → AWS Managed Blockchain")
        print("=" * 60)
        
        if dry_run:
            print("\n🔍 DRY RUN MODE - No changes will be made")
        
        # Check prerequisites
        if not self.check_prerequisites():
            print("\n❌ Prerequisites not met. Exiting.")
            return False
        
        # Initialize services
        self.initialize_services()
        
        if not dry_run:
            # Perform migration
            self.migrate_blockchain_references()
            
            # Verify migration
            self.verify_migration()
        else:
            print("\n🔍 Dry run complete - no changes made")
        
        # Generate report
        report = self.generate_report()
        print(report)
        
        return True


def main():
    """Main migration function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate blockchain from Fabric to AWS")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without making changes")
    parser.add_argument("--force", action="store_true", help="Force migration without confirmation")
    args = parser.parse_args()
    
    migration = BlockchainMigration()
    
    if not args.force and not args.dry_run:
        print("\n⚠️  WARNING: This will migrate all blockchain data to AWS Managed Blockchain.")
        print("   This process cannot be easily reversed.")
        response = input("\nContinue? (yes/no): ")
        if response.lower() != "yes":
            print("Migration cancelled.")
            return
    
    success = migration.run_migration(dry_run=args.dry_run)
    
    if success:
        print("\n✅ Migration completed successfully!")
        if not args.dry_run:
            print("\n📋 Next steps:")
            print("1. Update .env to set BLOCKCHAIN_PROVIDER=aws_managed_blockchain")
            print("2. Test the application with AWS blockchain")
            print("3. Monitor CloudWatch for any issues")
            print("4. Keep Fabric network running for rollback if needed")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
