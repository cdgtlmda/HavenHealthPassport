"""
Security Monitoring Deployment for Haven Health Passport.

CRITICAL: This module deploys comprehensive security monitoring
for the healthcare system including:
- Real-time threat detection
- Compliance monitoring (HIPAA)
- Audit trail analysis
- Anomaly detection
"""

import io
import json
import zipfile
from datetime import datetime
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SecurityMonitoringDeployment:
    """
    Deploys and configures security monitoring infrastructure.

    Components:
    - AWS GuardDuty for threat detection
    - AWS Security Hub for centralized monitoring
    - CloudWatch alarms for security events
    - Lambda functions for automated response
    """

    def __init__(self) -> None:
        """Initialize security monitoring deployment with AWS clients."""
        self.environment = settings.environment.lower()
        self.region = settings.aws_region

        # AWS clients
        self.guardduty_client = boto3.client("guardduty", region_name=self.region)
        self.securityhub_client = boto3.client("securityhub", region_name=self.region)
        self.cloudwatch_client = boto3.client("cloudwatch", region_name=self.region)
        self.lambda_client = boto3.client("lambda", region_name=self.region)
        self.sns_client = boto3.client("sns", region_name=self.region)
        self.iam_client = boto3.client("iam", region_name=self.region)

        logger.info(
            f"Initialized Security Monitoring Deployment for {self.environment}"
        )

    def deploy_guardduty(self) -> str:
        """Deploy AWS GuardDuty for threat detection."""
        logger.info("Deploying AWS GuardDuty...")

        try:
            # Create GuardDuty detector
            response = self.guardduty_client.create_detector(
                Enable=True,
                FindingPublishingFrequency="FIFTEEN_MINUTES",
                DataSources={
                    "S3Logs": {"Enable": True},
                    "Kubernetes": {"AuditLogs": {"Enable": True}},
                },
                Tags={
                    "Project": "HavenHealthPassport",
                    "Environment": self.environment,
                    "Compliance": "HIPAA",
                },
            )

            detector_id = str(response["DetectorId"])
            logger.info(f"Created GuardDuty detector: {detector_id}")

            # Configure threat intel sets for healthcare-specific threats
            self._configure_threat_intel(detector_id)

            # Set up SNS notifications for high-severity findings
            self._configure_guardduty_notifications(detector_id)

            return detector_id

        except self.guardduty_client.exceptions.BadRequestException as e:
            if "already exists" in str(e):
                # Get existing detector
                detectors = self.guardduty_client.list_detectors()
                if detectors["DetectorIds"]:
                    detector_id = str(detectors["DetectorIds"][0])
                    logger.info(f"Using existing GuardDuty detector: {detector_id}")
                    return detector_id
            raise

    def _configure_threat_intel(self, detector_id: str) -> None:
        """Configure healthcare-specific threat intelligence."""
        _ = detector_id  # Will be used for GuardDuty threat intel configuration
        # Create S3 bucket for threat intel
        s3_client = boto3.client("s3", region_name=self.region)
        threat_intel_bucket = f"haven-health-{self.environment}-threat-intel"

        try:
            s3_client.create_bucket(
                Bucket=threat_intel_bucket,
                CreateBucketConfiguration=(
                    {"LocationConstraint": self.region}
                    if self.region != "us-east-1"
                    else {}
                ),
            )

            # Enable versioning and encryption
            s3_client.put_bucket_versioning(
                Bucket=threat_intel_bucket,
                VersioningConfiguration={"Status": "Enabled"},
            )

            s3_client.put_bucket_encryption(
                Bucket=threat_intel_bucket,
                ServerSideEncryptionConfiguration={
                    "Rules": [
                        {
                            "ApplyServerSideEncryptionByDefault": {
                                "SSEAlgorithm": "aws:kms",
                                "KMSMasterKeyID": getattr(
                                    settings, "kms_key_id", "alias/aws/s3"
                                ),
                            }
                        }
                    ]
                },
            )

            logger.info(f"Created threat intel bucket: {threat_intel_bucket}")

        except s3_client.exceptions.BucketAlreadyExists:
            logger.info(f"Using existing threat intel bucket: {threat_intel_bucket}")

    def _configure_guardduty_notifications(self, detector_id: str) -> None:
        """Configure notifications for GuardDuty findings."""
        _ = detector_id  # Will be used for CloudWatch Events rule configuration
        # Create SNS topic for security alerts
        topic_name = f"haven-health-{self.environment}-security-alerts"

        try:
            response = self.sns_client.create_topic(
                Name=topic_name,
                Attributes={
                    "DisplayName": "Haven Health Security Alerts",
                    "KmsMasterKeyId": getattr(settings, "kms_key_id", "alias/aws/sns"),
                },
                Tags=[
                    {"Key": "Project", "Value": "HavenHealthPassport"},
                    {"Key": "Environment", "Value": self.environment},
                    {"Key": "Purpose", "Value": "Security Monitoring"},
                ],
            )
            topic_arn = response["TopicArn"]
            logger.info(f"Created security alerts topic: {topic_arn}")

        except self.sns_client.exceptions.TopicAlreadyExistsException:
            # Get existing topic
            topics = self.sns_client.list_topics()
            topic_arn = next(
                t["TopicArn"] for t in topics["Topics"] if topic_name in t["TopicArn"]
            )
            logger.info(f"Using existing security alerts topic: {topic_arn}")

    def deploy_security_hub(self) -> Dict[str, Any]:
        """Deploy AWS Security Hub for centralized security management."""
        logger.info("Deploying AWS Security Hub...")

        try:
            # Enable Security Hub
            response = self.securityhub_client.enable_security_hub(
                Tags={
                    "Project": "HavenHealthPassport",
                    "Environment": self.environment,
                    "Compliance": "HIPAA",
                },
                EnableDefaultStandards=True,
            )

            hub_arn = response["HubArn"]
            logger.info(f"Enabled Security Hub: {hub_arn}")

            # Enable HIPAA compliance standard
            self._enable_hipaa_standard()

            # Configure custom insights for healthcare
            self._create_healthcare_insights()

            return {"hub_arn": hub_arn, "status": "enabled"}

        except self.securityhub_client.exceptions.ResourceConflictException:
            logger.info("Security Hub already enabled")
            return {"hub_arn": "already-enabled", "status": "existing"}

    def _enable_hipaa_standard(self) -> None:
        """Enable HIPAA compliance standard in Security Hub."""
        try:
            # Get available standards
            standards = self.securityhub_client.describe_standards()

            # Find HIPAA standard
            hipaa_standard = next(
                (s for s in standards["Standards"] if "HIPAA" in s["Name"]), None
            )

            if hipaa_standard:
                # Enable HIPAA standard
                self.securityhub_client.batch_enable_standards(
                    StandardsSubscriptionRequests=[
                        {"StandardsArn": hipaa_standard["StandardsArn"]}
                    ]
                )
                logger.info("Enabled HIPAA compliance standard")
            else:
                logger.warning(
                    "HIPAA standard not found - manual configuration required"
                )

        except (ClientError, KeyError, StopIteration) as e:
            logger.error(f"Error enabling HIPAA standard: {e}")

    def _create_healthcare_insights(self) -> None:
        """Create custom Security Hub insights for healthcare."""
        insights = [
            {
                "name": "PHI Access Anomalies",
                "filters": {
                    "ResourceType": [{"Value": "AwsS3Bucket", "Comparison": "EQUALS"}],
                    "ComplianceStatus": [{"Value": "FAILED", "Comparison": "EQUALS"}],
                    "RecordState": [{"Value": "ACTIVE", "Comparison": "EQUALS"}],
                },
                "group_by": "ResourceId",
            },
            {
                "name": "Failed Authentication Attempts",
                "filters": {
                    "Type": [{"Value": "Authentication", "Comparison": "PREFIX"}],
                    "Severity": [{"Value": "HIGH", "Comparison": "EQUALS"}],
                },
                "group_by": "AwsAccountId",
            },
        ]

        for insight_config in insights:
            try:
                self.securityhub_client.create_insight(
                    Name=f"Haven Health - {insight_config['name']}",
                    Filters=insight_config["filters"],
                    GroupByAttribute=insight_config["group_by"],
                )
                logger.info(f"Created insight: {insight_config['name']}")
            except (ClientError, KeyError, ValueError) as e:
                logger.warning(
                    f"Could not create insight {insight_config['name']}: {e}"
                )

    def deploy_cloudwatch_alarms(self) -> List[str]:
        """Deploy CloudWatch alarms for security monitoring."""
        logger.info("Deploying CloudWatch security alarms...")

        alarms = []

        # Failed login attempts alarm
        alarms.append(
            self._create_alarm(
                name=f"haven-health-{self.environment}-failed-logins",
                description="Alert on multiple failed login attempts",
                metric_name="FailedLoginAttempts",
                namespace="HavenHealth/Security",
                statistic="Sum",
                period=300,  # 5 minutes
                evaluation_periods=1,
                threshold=5,
                comparison_operator="GreaterThanThreshold",
            )
        )

        # Unauthorized PHI access alarm
        alarms.append(
            self._create_alarm(
                name=f"haven-health-{self.environment}-unauthorized-phi-access",
                description="Alert on unauthorized PHI access attempts",
                metric_name="UnauthorizedPHIAccess",
                namespace="HavenHealth/Security",
                statistic="Sum",
                period=60,  # 1 minute
                evaluation_periods=1,
                threshold=1,
                comparison_operator="GreaterThanOrEqualToThreshold",
            )
        )

        # Encryption failures alarm
        alarms.append(
            self._create_alarm(
                name=f"haven-health-{self.environment}-encryption-failures",
                description="Alert on encryption/decryption failures",
                metric_name="EncryptionFailures",
                namespace="HavenHealth/Security",
                statistic="Sum",
                period=300,
                evaluation_periods=2,
                threshold=3,
                comparison_operator="GreaterThanThreshold",
            )
        )

        # API rate limit alarm
        alarms.append(
            self._create_alarm(
                name=f"haven-health-{self.environment}-api-rate-limit",
                description="Alert on API rate limit violations",
                metric_name="APIRateLimitExceeded",
                namespace="HavenHealth/API",
                statistic="Sum",
                period=60,
                evaluation_periods=1,
                threshold=10,
                comparison_operator="GreaterThanThreshold",
            )
        )

        logger.info(f"Created {len(alarms)} security alarms")
        return alarms

    def _create_alarm(self, **kwargs: Any) -> str:
        """Create a CloudWatch alarm."""
        try:
            # Get or create SNS topic for alarms
            topic_arn = self._get_alarm_topic()

            self.cloudwatch_client.put_metric_alarm(
                AlarmName=kwargs["name"],
                AlarmDescription=kwargs["description"],
                ActionsEnabled=True,
                AlarmActions=[topic_arn],
                MetricName=kwargs["metric_name"],
                Namespace=kwargs["namespace"],
                Statistic=kwargs["statistic"],
                Period=kwargs["period"],
                EvaluationPeriods=kwargs["evaluation_periods"],
                Threshold=kwargs["threshold"],
                ComparisonOperator=kwargs["comparison_operator"],
                TreatMissingData="notBreaching",
                Tags=[
                    {"Key": "Project", "Value": "HavenHealthPassport"},
                    {"Key": "Environment", "Value": self.environment},
                    {"Key": "Type", "Value": "Security"},
                ],
            )

            alarm_name: str = kwargs["name"]
            logger.info(f"Created alarm: {alarm_name}")
            return alarm_name

        except Exception as e:
            logger.error(f"Error creating alarm {kwargs['name']}: {e}")
            raise

    def _get_alarm_topic(self) -> str:
        """Get or create SNS topic for CloudWatch alarms."""
        topic_name = f"haven-health-{self.environment}-cloudwatch-alarms"

        topics = self.sns_client.list_topics()
        for topic in topics["Topics"]:
            if topic_name in topic["TopicArn"]:
                topic_arn: str = topic["TopicArn"]
                return topic_arn

        # Create new topic
        response = self.sns_client.create_topic(Name=topic_name)
        new_topic_arn: str = response["TopicArn"]
        return new_topic_arn

    def deploy_automated_response(self) -> str:
        """Deploy Lambda function for automated security response."""
        logger.info("Deploying automated security response Lambda...")

        # Create IAM role for Lambda
        role_arn = self._create_lambda_role()

        # Create Lambda function
        function_name = f"haven-health-{self.environment}-security-response"

        # Lambda code for automated response
        lambda_code = '''
import json
import boto3
import os
from datetime import datetime

def lambda_handler(event, context):
    """Automated response to security events."""
    # Parse security event
    if 'source' in event and event['source'] == 'aws.guardduty':
        return handle_guardduty_finding(event)
    elif 'source' in event and event['source'] == 'aws.securityhub':
        return handle_security_hub_finding(event)
    else:
        return handle_custom_alert(event)

def handle_guardduty_finding(event):
    """Handle GuardDuty findings."""
    finding = event['detail']
    severity = finding['severity']
    # High severity actions
    if severity >= 7:
        # Isolate affected resource
        if finding['resource']['type'] == 'Instance':
            isolate_instance(finding['resource']['instanceDetails']['instanceId'])
        # Notify security team
        notify_security_team(finding, 'CRITICAL')

        # Create incident ticket
        create_incident(finding)
    
    return {
        'statusCode': 200,
        'body': json.dumps('GuardDuty finding processed')
    }

def handle_security_hub_finding(event):
    """Handle Security Hub findings."""
    finding = event['detail']['findings'][0]
    if finding['Compliance']['Status'] == 'FAILED':
        # Log compliance failure
        log_compliance_failure(finding)

        # Auto-remediate if possible
        if finding['ProductArn'].endswith('s3'):
            remediate_s3_finding(finding)

    return {
        'statusCode': 200,
        'body': json.dumps('Security Hub finding processed')
    }

def handle_custom_alert(event):
    """Handle custom security alerts."""
    alert_type = event.get('alertType', 'unknown')

    if alert_type == 'failed_login':
        # Block IP after threshold
        block_suspicious_ip(event['sourceIp'])
    elif alert_type == 'unauthorized_phi_access':
        # Revoke access immediately
        revoke_user_access(event['userId'])
        # Audit trail
        create_security_audit(event)

    return {
        'statusCode': 200,
        'body': json.dumps(f'Handled {alert_type} alert')
    }

def isolate_instance(instance_id):
    """Isolate compromised EC2 instance."""
    ec2 = boto3.client('ec2')

    # Create isolation security group
    isolation_sg = ec2.create_security_group(
        GroupName=f'isolation-{instance_id}-{datetime.utcnow().timestamp()}',
        Description='Security isolation group - no traffic allowed'
    )

    # Apply to instance
    ec2.modify_instance_attribute(
        InstanceId=instance_id,
        Groups=[isolation_sg['GroupId']]
    )

def notify_security_team(finding, level):
    """Send notification to security team."""
    sns = boto3.client('sns')
    topic_arn = os.environ['SECURITY_TOPIC_ARN']

    sns.publish(
        TopicArn=topic_arn,
        Subject=f'{level}: Security Finding - {finding["type"]}',
        Message=json.dumps(finding, indent=2)
    )
'''

        try:
            # Create deployment package
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr("lambda_function.py", lambda_code)

            zip_buffer.seek(0)

            # Create Lambda function
            response = self.lambda_client.create_function(
                FunctionName=function_name,
                Runtime="python3.9",
                Role=role_arn,
                Handler="lambda_function.lambda_handler",
                Code={"ZipFile": zip_buffer.read()},
                Description="Automated security incident response",
                Timeout=300,
                MemorySize=512,
                Environment={
                    "Variables": {
                        "ENVIRONMENT": self.environment,
                        "SECURITY_TOPIC_ARN": self._get_alarm_topic(),
                    }
                },
                Tags={
                    "Project": "HavenHealthPassport",
                    "Environment": self.environment,
                    "Purpose": "Security Response",
                },
            )

            function_arn = response["FunctionArn"]
            logger.info(f"Created security response Lambda: {function_arn}")

            # Configure event sources
            self._configure_lambda_triggers(function_arn)

            arn: str = function_arn
            return arn

        except self.lambda_client.exceptions.ResourceConflictException:
            logger.info("Security response Lambda already exists")
            response = self.lambda_client.get_function(FunctionName=function_name)
            config_arn: str = response["Configuration"]["FunctionArn"]
            return config_arn

    def _create_lambda_role(self) -> str:
        """Create IAM role for Lambda security response."""
        role_name = f"haven-health-{self.environment}-security-lambda-role"

        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        try:
            response = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Role for Haven Health security response Lambda",
                Tags=[
                    {"Key": "Project", "Value": "HavenHealthPassport"},
                    {"Key": "Environment", "Value": self.environment},
                ],
            )

            role_arn = response["Role"]["Arn"]

            # Attach necessary policies
            policies = [
                "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                "arn:aws:iam::aws:policy/AmazonEC2FullAccess",
                "arn:aws:iam::aws:policy/AmazonSNSFullAccess",
                "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
            ]

            for policy_arn in policies:
                self.iam_client.attach_role_policy(
                    RoleName=role_name, PolicyArn=policy_arn
                )

            logger.info(f"Created Lambda role: {role_arn}")
            arn: str = role_arn
            return arn

        except self.iam_client.exceptions.EntityAlreadyExistsException:
            response = self.iam_client.get_role(RoleName=role_name)
            role_arn_response: str = response["Role"]["Arn"]
            return role_arn_response

    def _configure_lambda_triggers(self, function_arn: str) -> None:
        """Configure event triggers for security Lambda."""
        # EventBridge rule for GuardDuty findings
        events_client = boto3.client("events", region_name=self.region)

        rule_name = f"haven-health-{self.environment}-guardduty-findings"

        try:
            response = events_client.put_rule(
                Name=rule_name,
                EventPattern=json.dumps(
                    {"source": ["aws.guardduty"], "detail-type": ["GuardDuty Finding"]}
                ),
                State="ENABLED",
                Description="Trigger security response for GuardDuty findings",
            )

            # Add Lambda permission
            self.lambda_client.add_permission(
                FunctionName=function_arn,
                StatementId=f"{rule_name}-permission",
                Action="lambda:InvokeFunction",
                Principal="events.amazonaws.com",
                SourceArn=response["RuleArn"],
            )

            # Add Lambda as target
            events_client.put_targets(
                Rule=rule_name, Targets=[{"Id": "1", "Arn": function_arn}]
            )

            logger.info("Configured GuardDuty trigger for Lambda")

        except (ClientError, KeyError, ValueError) as e:
            logger.error(f"Error configuring Lambda triggers: {e}")

    def deploy_all(self) -> Dict[str, Any]:
        """Deploy complete security monitoring infrastructure."""
        logger.info("Deploying complete security monitoring infrastructure...")

        results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "environment": self.environment,
            "components": {},
        }

        try:
            # Deploy GuardDuty
            detector_id = self.deploy_guardduty()
            results["components"]["guardduty"] = {
                "status": "deployed",
                "detector_id": detector_id,
            }
        except (ClientError, ValueError, RuntimeError) as e:
            logger.error(f"GuardDuty deployment failed: {e}")
            results["components"]["guardduty"] = {"status": "failed", "error": str(e)}

        try:
            # Deploy Security Hub
            security_hub = self.deploy_security_hub()
            results["components"]["security_hub"] = security_hub
        except (ClientError, ValueError, RuntimeError) as e:
            logger.error(f"Security Hub deployment failed: {e}")
            results["components"]["security_hub"] = {
                "status": "failed",
                "error": str(e),
            }

        try:
            # Deploy CloudWatch alarms
            alarms = self.deploy_cloudwatch_alarms()
            results["components"]["cloudwatch_alarms"] = {
                "status": "deployed",
                "alarms": alarms,
            }
        except (ClientError, ValueError, RuntimeError) as e:
            logger.error(f"CloudWatch alarms deployment failed: {e}")
            results["components"]["cloudwatch_alarms"] = {
                "status": "failed",
                "error": str(e),
            }

        try:
            # Deploy automated response
            lambda_arn = self.deploy_automated_response()
            results["components"]["automated_response"] = {
                "status": "deployed",
                "lambda_arn": lambda_arn,
            }
        except (ClientError, ValueError, RuntimeError) as e:
            logger.error(f"Automated response deployment failed: {e}")
            results["components"]["automated_response"] = {
                "status": "failed",
                "error": str(e),
            }

        # Summary
        deployed = sum(
            1 for c in results["components"].values() if c.get("status") == "deployed"
        )
        failed = sum(
            1 for c in results["components"].values() if c.get("status") == "failed"
        )

        results["summary"] = {
            "total_components": len(results["components"]),
            "deployed": deployed,
            "failed": failed,
        }

        logger.info(
            f"Security monitoring deployment complete: {deployed} deployed, {failed} failed"
        )
        return results


# Module-level singleton instance
_security_monitoring_instance = None


def get_security_monitoring_deployment() -> SecurityMonitoringDeployment:
    """Get the security monitoring deployment instance."""
    global _security_monitoring_instance
    if _security_monitoring_instance is None:
        _security_monitoring_instance = SecurityMonitoringDeployment()
    return _security_monitoring_instance
