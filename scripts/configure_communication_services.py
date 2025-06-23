#!/usr/bin/env python3
"""
Communication Services Configuration for Haven Health Passport
Configures SMS, email, and push notification services for patient communication
CRITICAL: Ensures refugees receive critical health notifications
"""

import os
import sys
import json
import boto3
import argparse
import logging
from datetime import datetime
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CommunicationServicesConfigurator:
    """Configures communication services for patient notifications"""
    
    def __init__(self, environment: str):
        self.environment = environment
        self.secrets_client = boto3.client('secretsmanager')
        self.ssm_client = boto3.client('ssm')
        
    def configure_twilio(self) -> bool:
        """Configure Twilio for SMS notifications"""
        print("\n" + "="*60)
        print("Configuring Twilio SMS Service")
        print("="*60)
        print("Twilio is used for critical health notifications to refugees")
        print("including appointment reminders and medication alerts.\n")
        
        account_sid = input("Enter Twilio Account SID: ").strip()
        auth_token = input("Enter Twilio Auth Token: ").strip()
        messaging_service_sid = input("Enter Twilio Messaging Service SID: ").strip()
        
        if not all([account_sid, auth_token, messaging_service_sid]):
            print("❌ All Twilio credentials are required")
            return False
        
        try:
            # Validate Twilio credentials
            auth = (account_sid, auth_token)
            response = requests.get(
                f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json',
                auth=auth,
                timeout=10
            )
            
            if response.status_code != 200:
                print("❌ Invalid Twilio credentials")
                return False
            
            # Store credentials
            secret_data = {
                'account_sid': account_sid,
                'auth_token': auth_token,
                'messaging_service_sid': messaging_service_sid,
                'configured_at': datetime.utcnow().isoformat()
            }
            
            secret_name = f"haven-health-passport/{self.environment}/twilio"
            
            try:
                self.secrets_client.create_secret(
                    Name=secret_name,
                    SecretString=json.dumps(secret_data),
                    Description=f"Twilio credentials for {self.environment}"
                )
            except self.secrets_client.exceptions.ResourceExistsException:
                self.secrets_client.update_secret(
                    SecretId=secret_name,
                    SecretString=json.dumps(secret_data)
                )
            
            print("✅ Twilio configured successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure Twilio: {str(e)}")
            print("❌ Failed to configure Twilio")
            return False
    
    def configure_aws_sns_backup(self) -> bool:
        """Configure AWS SNS as SMS backup provider"""
        print("\n" + "="*60)
        print("Configuring AWS SNS (SMS Backup)")
        print("="*60)
        print("AWS SNS serves as backup for critical notifications")
        print("when Twilio is unavailable.\n")
        
        try:
            # Create SNS client
            sns_client = boto3.client('sns')
            
            # Set SMS preferences
            sns_client.set_sms_attributes(
                attributes={
                    'DefaultSMSType': 'Transactional',  # Priority delivery
                    'UsageReportS3Bucket': f'haven-health-{self.environment}-sms-logs'
                }
            )
            
            # Store configuration
            config_data = {
                'enabled': True,
                'default_sender_id': 'HavenHealth',
                'configured_at': datetime.utcnow().isoformat()
            }
            
            self.ssm_client.put_parameter(
                Name=f"/haven-health/{self.environment}/sns/sms-config",
                Value=json.dumps(config_data),
                Type='String',
                Overwrite=True
            )
            
            print("✅ AWS SNS backup configured successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure AWS SNS: {str(e)}")
            print("❌ Failed to configure AWS SNS")
            return False
    
    def configure_push_notifications(self) -> bool:
        """Configure push notifications for mobile apps"""
        print("\n" + "="*60)
        print("Configuring Push Notifications")
        print("="*60)
        
        # iOS Configuration
        print("\n📱 iOS Push Notifications (APNs)")
        ios_cert_path = input("Enter path to APNs certificate (.p12): ").strip()
        ios_cert_password = input("Enter certificate password: ").strip()
        ios_bundle_id = input("Enter iOS bundle ID: ").strip()
        
        # Android Configuration
        print("\n🤖 Android Push Notifications (FCM)")
        fcm_server_key = input("Enter FCM Server Key: ").strip()
        android_package_name = input("Enter Android package name: ").strip()
        
        try:
            config_data = {
                'ios': {
                    'bundle_id': ios_bundle_id,
                    'cert_uploaded': bool(ios_cert_path),
                    'environment': 'production' if self.environment == 'production' else 'sandbox'
                },
                'android': {
                    'package_name': android_package_name,
                    'fcm_configured': bool(fcm_server_key)
                },
                'configured_at': datetime.utcnow().isoformat()
            }
            
            # Store FCM key securely
            if fcm_server_key:
                secret_name = f"haven-health-passport/{self.environment}/fcm"
                try:
                    self.secrets_client.create_secret(
                        Name=secret_name,
                        SecretString=json.dumps({'server_key': fcm_server_key}),
                        Description=f"FCM credentials for {self.environment}"
                    )
                except self.secrets_client.exceptions.ResourceExistsException:
                    self.secrets_client.update_secret(
                        SecretId=secret_name,
                        SecretString=json.dumps({'server_key': fcm_server_key})
                    )
            
            # Store configuration
            self.ssm_client.put_parameter(
                Name=f"/haven-health/{self.environment}/push-notifications/config",
                Value=json.dumps(config_data),
                Type='String',
                Overwrite=True
            )
            
            print("✅ Push notifications configured")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure push notifications: {str(e)}")
            print("❌ Failed to configure push notifications")
            return False
    
    def configure_email_templates(self) -> bool:
        """Configure email templates for patient communications"""
        print("\n" + "="*60)
        print("Configuring Email Templates")
        print("="*60)
        
        try:
            ses_client = boto3.client('ses')
            
            # Critical email templates for refugee healthcare
            templates = [
                {
                    'name': f'haven-health-{self.environment}-appointment-reminder',
                    'subject': 'Healthcare Appointment Reminder - {{PatientName}}',
                    'html': '''<html>
<body>
<h2>Appointment Reminder</h2>
<p>Dear {{PatientName}},</p>
<p>This is a reminder about your upcoming appointment:</p>
<ul>
<li><strong>Date:</strong> {{AppointmentDate}}</li>
<li><strong>Time:</strong> {{AppointmentTime}}</li>
<li><strong>Location:</strong> {{ClinicName}}</li>
<li><strong>Provider:</strong> {{ProviderName}}</li>
</ul>
<p>Please bring your Haven Health ID and any current medications.</p>
<p>If you need to reschedule, please contact us immediately.</p>
</body>
</html>''',
                    'text': '''Appointment Reminder

Dear {{PatientName}},

This is a reminder about your upcoming appointment:
- Date: {{AppointmentDate}}
- Time: {{AppointmentTime}}
- Location: {{ClinicName}}
- Provider: {{ProviderName}}

Please bring your Haven Health ID and any current medications.'''
                },
                {
                    'name': f'haven-health-{self.environment}-medication-alert',
                    'subject': 'Important Medication Alert - {{PatientName}}',
                    'html': '''<html>
<body style="background-color: #fff3cd; padding: 20px;">
<h2 style="color: #856404;">⚠️ Important Medication Alert</h2>
<p>Dear {{PatientName}},</p>
<p><strong>{{AlertMessage}}</strong></p>
<p>Please contact your healthcare provider immediately if you have questions.</p>
<p>Emergency Contact: {{EmergencyPhone}}</p>
</body>
</html>''',
                    'text': '''⚠️ Important Medication Alert

Dear {{PatientName}},

{{AlertMessage}}

Please contact your healthcare provider immediately if you have questions.
Emergency Contact: {{EmergencyPhone}}'''
                }
            ]
            
            for template in templates:
                try:
                    ses_client.create_template(
                        Template={
                            'TemplateName': template['name'],
                            'SubjectPart': template['subject'],
                            'HtmlPart': template['html'],
                            'TextPart': template['text']
                        }
                    )
                    print(f"✅ Created template: {template['name']}")
                except ses_client.exceptions.AlreadyExistsException:
                    # Update existing template
                    ses_client.update_template(
                        Template={
                            'TemplateName': template['name'],
                            'SubjectPart': template['subject'],
                            'HtmlPart': template['html'],
                            'TextPart': template['text']
                        }
                    )
                    print(f"✅ Updated template: {template['name']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure email templates: {str(e)}")
            print("❌ Failed to configure email templates")
            return False
    
    def configure_all_services(self) -> None:
        """Configure all communication services"""
        print("\n" + "="*80)
        print("Haven Health Passport - Communication Services Configuration")
        print(f"Environment: {self.environment.upper()}")
        print("="*80)
        print("\n⚠️  CRITICAL: These services deliver health notifications to refugees.")
        print("Proper configuration ensures patients receive critical health alerts.\n")
        
        results = {
            'Twilio SMS': self.configure_twilio(),
            'AWS SNS Backup': self.configure_aws_sns_backup(),
            'Push Notifications': self.configure_push_notifications(),
            'Email Templates': self.configure_email_templates()
        }
        
        # Summary
        print("\n" + "="*80)
        print("Configuration Summary")
        print("="*80)
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        for service, success in results.items():
            status = "✅ Configured" if success else "❌ Failed"
            print(f"{service}: {status}")
        
        print(f"\nTotal: {success_count}/{total_count} services configured successfully")
        
        if success_count == total_count:
            print("\n✅ All communication services configured successfully!")
            print("\nNext steps:")
            print("1. Test SMS delivery to verify configuration")
            print("2. Send test push notifications")
            print("3. Verify email template rendering")
            print("4. Configure notification preferences in application")
        else:
            print("\n⚠️  WARNING: Some services failed to configure.")
            print("Patients may not receive critical notifications!")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Configure communication services for Haven Health Passport'
    )
    parser.add_argument(
        '--environment',
        choices=['development', 'staging', 'production'],
        required=True,
        help='Target environment for configuration'
    )
    
    args = parser.parse_args()
    
    # Production safety check
    if args.environment == 'production':
        print("\n⚠️  WARNING: Configuring PRODUCTION communication services!")
        print("This will affect real patient notifications.")
        confirm = input("Type 'CONFIGURE PRODUCTION' to continue: ")
        if confirm != 'CONFIGURE PRODUCTION':
            print("Configuration cancelled.")
            sys.exit(0)
    
    # Check AWS credentials
    try:
        boto3.client('sts').get_caller_identity()
    except Exception as e:
        print(f"\n❌ AWS credentials not configured: {str(e)}")
        print("Please configure AWS credentials before running this script.")
        sys.exit(1)
    
    # Run configuration
    configurator = CommunicationServicesConfigurator(args.environment)
    configurator.configure_all_services()


if __name__ == '__main__':
    main()
