"""Database infrastructure setup for PostgreSQL on AWS RDS."""

import json
import os
import secrets
import tempfile
import time
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

try:
    import psycopg2
except ImportError:
    psycopg2 = None

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class DatabaseInfrastructure:
    """Manages PostgreSQL RDS infrastructure setup and configuration."""

    def __init__(self) -> None:
        """Initialize database infrastructure manager."""
        self.region = settings.aws_region
        self.rds_client = boto3.client("rds", region_name=self.region)
        self.ec2_client = boto3.client("ec2", region_name=self.region)
        self.cloudwatch_client = boto3.client("cloudwatch", region_name=self.region)

        # RDS configuration
        self.db_identifier = "haven-health-db"
        self.db_name = "haven_health"
        self.master_username = "haven_admin"
        self.db_instance_class = "db.t3.medium"
        self.allocated_storage = 100  # GB
        self.max_allocated_storage = 1000  # GB for autoscaling

        # Connection pool configuration
        self.pool_size = 20
        self.max_overflow = 10
        self.pool_timeout = 30
        self.pool_recycle = 3600

    def setup_postgresql_rds(self) -> Optional[str]:
        """Set up PostgreSQL on RDS with Multi-AZ deployment."""
        try:
            # Check if DB instance already exists
            try:
                response = self.rds_client.describe_db_instances(
                    DBInstanceIdentifier=self.db_identifier
                )
                if response["DBInstances"]:
                    logger.info(f"RDS instance already exists: {self.db_identifier}")
                    endpoint_address: str = response["DBInstances"][0]["Endpoint"][
                        "Address"
                    ]
                    return endpoint_address
            except ClientError as e:
                if e.response["Error"]["Code"] != "DBInstanceNotFound":
                    raise

            # Create subnet group
            subnet_group_name = self._create_db_subnet_group()

            # Create security group
            security_group_id = self._create_db_security_group()

            # Create parameter group for optimized settings
            param_group_name = self._create_db_parameter_group()

            # Generate secure password
            master_password = secrets.token_urlsafe(32)

            # Store password in Secrets Manager
            self._store_db_credentials(master_password)

            # Create RDS instance
            response = self.rds_client.create_db_instance(
                DBInstanceIdentifier=self.db_identifier,
                DBName=self.db_name,
                DBInstanceClass=self.db_instance_class,
                Engine="postgres",
                EngineVersion="14.7",
                MasterUsername=self.master_username,
                MasterUserPassword=master_password,
                AllocatedStorage=self.allocated_storage,
                MaxAllocatedStorage=self.max_allocated_storage,  # Enable autoscaling
                StorageType="gp3",
                StorageEncrypted=True,
                MultiAZ=True,  # Multi-AZ deployment
                DBSubnetGroupName=subnet_group_name,
                VpcSecurityGroupIds=[security_group_id],
                DBParameterGroupName=param_group_name,
                BackupRetentionPeriod=35,  # 35 days retention
                PreferredBackupWindow="03:00-04:00",
                PreferredMaintenanceWindow="sun:04:00-sun:05:00",
                EnablePerformanceInsights=True,
                PerformanceInsightsRetentionPeriod=7,
                MonitoringInterval=60,
                MonitoringRoleArn=self._create_monitoring_role(),
                EnableCloudwatchLogsExports=["postgresql"],
                DeletionProtection=True,
                CopyTagsToSnapshot=True,
                Tags=[
                    {"Key": "Project", "Value": "HavenHealth"},
                    {"Key": "Environment", "Value": settings.environment},
                    {"Key": "ManagedBy", "Value": "Terraform"},
                ],
            )

            # Wait for instance to be available
            logger.info("Waiting for RDS instance to be available...")
            waiter = self.rds_client.get_waiter("db_instance_available")
            waiter.wait(DBInstanceIdentifier=self.db_identifier)

            # Get endpoint
            response = self.rds_client.describe_db_instances(
                DBInstanceIdentifier=self.db_identifier
            )
            endpoint = response["DBInstances"][0]["Endpoint"]["Address"]

            logger.info(f"PostgreSQL RDS instance created: {endpoint}")

            # Set up initial database schema
            self._initialize_database_schema(endpoint, master_password)

            typed_endpoint: str = endpoint
            return typed_endpoint

        except (ValueError, OSError, KeyError) as e:
            logger.error("Failed to set up PostgreSQL RDS: %s", str(e), exc_info=True)
            return None

    def _create_db_subnet_group(self) -> str:
        """Create DB subnet group for RDS."""
        subnet_group_name = f"{self.db_identifier}-subnet-group"

        try:
            # Check if subnet group exists
            try:
                self.rds_client.describe_db_subnet_groups(
                    DBSubnetGroupName=subnet_group_name
                )
                return subnet_group_name
            except ClientError:
                pass

            # Get VPC and subnets
            response = self.ec2_client.describe_vpcs(
                Filters=[{"Name": "isDefault", "Values": ["true"]}]
            )
            vpc_id = response["Vpcs"][0]["VpcId"]

            # Get private subnets in different AZs
            response = self.ec2_client.describe_subnets(
                Filters=[
                    {"Name": "vpc-id", "Values": [vpc_id]},
                    {"Name": "state", "Values": ["available"]},
                ]
            )

            subnet_ids = [subnet["SubnetId"] for subnet in response["Subnets"][:2]]

            # Create subnet group
            self.rds_client.create_db_subnet_group(
                DBSubnetGroupName=subnet_group_name,
                DBSubnetGroupDescription="Subnet group for Haven Health RDS",
                SubnetIds=subnet_ids,
                Tags=[{"Key": "Project", "Value": "HavenHealth"}],
            )

            logger.info(f"Created DB subnet group: {subnet_group_name}")
            return subnet_group_name

        except Exception as e:
            logger.error(f"Failed to create DB subnet group: {e}")
            raise

    def _create_db_security_group(self) -> str:
        """Create security group for database."""
        try:
            # Get VPC
            response = self.ec2_client.describe_vpcs(
                Filters=[{"Name": "isDefault", "Values": ["true"]}]
            )
            vpc_id = response["Vpcs"][0]["VpcId"]

            # Create security group
            response = self.ec2_client.create_security_group(
                GroupName=f"{self.db_identifier}-sg",
                Description="Security group for Haven Health RDS",
                VpcId=vpc_id,
            )

            security_group_id = response["GroupId"]

            # Add ingress rules
            self.ec2_client.authorize_security_group_ingress(
                GroupId=security_group_id,
                IpPermissions=[
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 5432,
                        "ToPort": 5432,
                        "IpRanges": [{"CidrIp": "10.0.0.0/8"}],  # VPC CIDR
                    }
                ],
            )

            logger.info(f"Created security group: {security_group_id}")
            sg_id: str = security_group_id
            return sg_id

        except ClientError as e:
            if e.response["Error"]["Code"] == "InvalidGroup.Duplicate":
                # Get existing security group
                response = self.ec2_client.describe_security_groups(
                    GroupNames=[f"{self.db_identifier}-sg"]
                )
                group_id: str = response["SecurityGroups"][0]["GroupId"]
                return group_id
            raise

    def _create_db_parameter_group(self) -> str:
        """Create optimized parameter group for PostgreSQL."""
        param_group_name = f"{self.db_identifier}-params"

        try:
            # Check if parameter group exists
            try:
                self.rds_client.describe_db_parameter_groups(
                    DBParameterGroupName=param_group_name
                )
                return param_group_name
            except ClientError:
                pass

            # Create parameter group
            self.rds_client.create_db_parameter_group(
                DBParameterGroupName=param_group_name,
                DBParameterGroupFamily="postgres14",
                Description="Optimized parameters for Haven Health PostgreSQL",
            )

            # Set optimized parameters
            parameters = [
                {
                    "ParameterName": "shared_preload_libraries",
                    "ParameterValue": "pg_stat_statements",
                },
                {"ParameterName": "log_statement", "ParameterValue": "all"},
                {
                    "ParameterName": "log_min_duration_statement",
                    "ParameterValue": "1000",
                },  # Log slow queries
                {"ParameterName": "max_connections", "ParameterValue": "200"},
                {"ParameterName": "work_mem", "ParameterValue": "16384"},  # 16MB
                {
                    "ParameterName": "maintenance_work_mem",
                    "ParameterValue": "65536",
                },  # 64MB
                {
                    "ParameterName": "effective_cache_size",
                    "ParameterValue": "3145728",
                },  # 3GB
                {
                    "ParameterName": "random_page_cost",
                    "ParameterValue": "1.1",
                },  # SSD optimized
                {"ParameterName": "wal_buffers", "ParameterValue": "2048"},  # 16MB
                {
                    "ParameterName": "checkpoint_completion_target",
                    "ParameterValue": "0.9",
                },
                {
                    "ParameterName": "autovacuum_vacuum_scale_factor",
                    "ParameterValue": "0.05",
                },
                {
                    "ParameterName": "autovacuum_analyze_scale_factor",
                    "ParameterValue": "0.02",
                },
            ]

            self.rds_client.modify_db_parameter_group(
                DBParameterGroupName=param_group_name, Parameters=parameters
            )

            logger.info(f"Created parameter group: {param_group_name}")
            return param_group_name

        except Exception as e:
            logger.error(f"Failed to create parameter group: {e}")
            raise

    def _create_monitoring_role(self) -> str:
        """Create IAM role for enhanced monitoring."""
        iam_client = boto3.client("iam")
        role_name = "rds-enhanced-monitoring-role"

        try:
            # Check if role exists
            try:
                response = iam_client.get_role(RoleName=role_name)
                role_arn: str = response["Role"]["Arn"]
                return role_arn
            except ClientError:
                pass

            # Create role
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "monitoring.rds.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }

            response = iam_client.create_role(
                RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust_policy)
            )

            # Attach policy
            iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole",
            )

            logger.info(f"Created monitoring role: {role_name}")
            role_arn = response["Role"]["Arn"]
            return role_arn

        except Exception as e:
            logger.error(f"Failed to create monitoring role: {e}")
            raise

    def _store_db_credentials(self, password: str) -> None:
        """Store database credentials in Secrets Manager."""
        secrets_client = boto3.client("secretsmanager", region_name=self.region)
        secret_name = f"rds/{self.db_identifier}/master"

        secret_value = json.dumps(
            {
                "username": self.master_username,
                "password": password,
                "engine": "postgres",
                "host": f"{self.db_identifier}.{self.region}.rds.amazonaws.com",
                "port": 5432,
                "dbname": self.db_name,
            }
        )

        try:
            secrets_client.create_secret(
                Name=secret_name,
                Description="Master credentials for Haven Health RDS",
                SecretString=secret_value,
                KmsKeyId="alias/aws/secretsmanager",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceExistsException":
                secrets_client.put_secret_value(
                    SecretId=secret_name, SecretString=secret_value
                )

    def _initialize_database_schema(self, endpoint: str, password: str) -> None:
        """Initialize database with required schemas."""
        try:
            # Wait a bit for DNS propagation
            time.sleep(30)

            # Connect to database
            conn = psycopg2.connect(
                host=endpoint,
                database=self.db_name,
                user=self.master_username,
                password=password,
                sslmode="require",
            )
            conn.autocommit = True
            cursor = conn.cursor()

            # Create schemas
            schemas = ["patient_data", "health_records", "verification", "audit"]
            for schema in schemas:
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

            # Create extensions
            extensions = ["uuid-ossp", "pgcrypto", "pg_stat_statements"]
            for ext in extensions:
                cursor.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext}"')

            # Create read-only user
            cursor.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'haven_readonly') THEN
                        CREATE USER haven_readonly WITH PASSWORD %s;
                    END IF;
                END $$;
            """,
                (secrets.token_urlsafe(32),),
            )

            # Grant permissions
            cursor.execute("GRANT CONNECT ON DATABASE haven_health TO haven_readonly")
            cursor.execute(
                "GRANT USAGE ON SCHEMA patient_data, health_records TO haven_readonly"
            )
            cursor.execute(
                "GRANT SELECT ON ALL TABLES IN SCHEMA patient_data, health_records TO haven_readonly"
            )

            logger.info("Initialized database schema")

            cursor.close()
            conn.close()

        except (psycopg2.Error, ValueError) as e:
            logger.error(
                "Failed to initialize database schema: %s", str(e), exc_info=True
            )

    def configure_connection_pool(self) -> Engine:
        """Configure SQLAlchemy connection pool with optimal settings."""
        # Get database URL from environment or construct it
        database_url = settings.database_url

        # Create engine with connection pooling
        engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
            pool_pre_ping=True,  # Verify connections before use
            echo_pool=settings.environment == "development",
            connect_args={
                "sslmode": "require",
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000",  # 30 second statement timeout
            },
        )

        # Add event listeners for monitoring
        @event.listens_for(engine, "connect")
        def receive_connect(dbapi_connection: Any, connection_record: Any) -> None:
            # Currently unused but required by SQLAlchemy event interface
            _ = dbapi_connection  # Acknowledge unused parameter
            connection_record.info["connect_time"] = datetime.utcnow()
            logger.debug("New database connection established")

        @event.listens_for(engine, "checkout")
        def receive_checkout(
            dbapi_connection: Any, connection_record: Any, connection_proxy: Any
        ) -> None:
            # Currently unused but required by SQLAlchemy event interface
            _ = (
                dbapi_connection,
                connection_record,
                connection_proxy,
            )  # Acknowledge unused parameters
            logger.debug("Connection checked out from pool")

        @event.listens_for(engine, "checkin")
        def receive_checkin(dbapi_connection: Any, connection_record: Any) -> None:
            # Currently unused but required by SQLAlchemy event interface
            _ = (dbapi_connection, connection_record)  # Acknowledge unused parameters
            logger.debug("Connection returned to pool")

        return engine

    def setup_automated_backups(self) -> bool:
        """Configure automated backup settings."""
        try:
            # Modify backup settings
            self.rds_client.modify_db_instance(
                DBInstanceIdentifier=self.db_identifier,
                BackupRetentionPeriod=35,  # 35 days
                PreferredBackupWindow="03:00-04:00",
                ApplyImmediately=True,
            )

            # Create backup vault in AWS Backup
            backup_client = boto3.client("backup", region_name=self.region)

            vault_name = "haven-health-backup-vault"
            try:
                backup_client.create_backup_vault(
                    BackupVaultName=vault_name,
                    EncryptionKeyArn=f'arn:aws:kms:{self.region}:{boto3.client("sts").get_caller_identity()["Account"]}:alias/aws/backup',
                )
            except ClientError as e:
                if e.response["Error"]["Code"] != "AlreadyExistsException":
                    raise

            # Create backup plan
            backup_plan = {
                "BackupPlanName": "haven-health-backup-plan",
                "Rules": [
                    {
                        "RuleName": "DailyBackups",
                        "TargetBackupVaultName": vault_name,
                        "ScheduleExpression": "cron(0 3 * * ? *)",  # Daily at 3 AM
                        "StartWindowMinutes": 60,
                        "CompletionWindowMinutes": 120,
                        "Lifecycle": {
                            "MoveToColdStorageAfterDays": 30,
                            "DeleteAfterDays": 365,  # Keep for 1 year
                        },
                        "RecoveryPointTags": {
                            "Project": "HavenHealth",
                            "Type": "DailyBackup",
                        },
                    }
                ],
            }

            try:
                backup_client.create_backup_plan(BackupPlan=backup_plan)
            except ClientError as e:
                if e.response["Error"]["Code"] == "AlreadyExistsException":
                    # Get existing plan
                    plans = backup_client.list_backup_plans()
                    next(
                        p["BackupPlanId"]
                        for p in plans["BackupPlansList"]
                        if p["BackupPlanName"] == "haven-health-backup-plan"
                    )
                else:
                    raise

            logger.info("Configured automated backups")
            return True

        except ClientError as e:
            logger.error("Failed to setup automated backups: %s", str(e), exc_info=True)
            return False

    def enable_point_in_time_recovery(self) -> bool:
        """Enable point-in-time recovery for the database."""
        try:
            # PITR is automatically enabled with automated backups
            # Verify it's enabled
            response = self.rds_client.describe_db_instances(
                DBInstanceIdentifier=self.db_identifier
            )

            db_instance = response["DBInstances"][0]
            if db_instance["BackupRetentionPeriod"] > 0:
                logger.info(
                    f"Point-in-time recovery enabled with {db_instance['BackupRetentionPeriod']} days retention"
                )
                return True
            else:
                logger.error("Point-in-time recovery not enabled")
                return False

        except ClientError as e:
            logger.error("Failed to verify PITR: %s", str(e), exc_info=True)
            return False

    def setup_ssl_tls(self) -> bool:
        """Configure SSL/TLS for secure connections."""
        try:
            # Download RDS CA certificate
            ca_cert_url = (
                "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem"
            )
            ca_cert_path = os.path.join(tempfile.gettempdir(), "rds-ca-2019-root.pem")

            # Validate URL scheme to prevent security issues
            parsed_url = urllib.parse.urlparse(ca_cert_url)
            if parsed_url.scheme not in ["https"]:
                raise ValueError(
                    "Only HTTPS URLs are allowed for certificate downloads"
                )

            # Use urlopen instead of urlretrieve for better security control
            req = urllib.request.Request(ca_cert_url)
            with urllib.request.urlopen(
                req
            ) as response:  # nosec B310 - URL is validated to be HTTPS only
                with open(ca_cert_path, "wb") as cert_file:
                    cert_file.write(response.read())

            # Update connection strings to use SSL
            os.environ["PGSSLMODE"] = "require"
            os.environ["PGSSLROOTCERT"] = ca_cert_path

            logger.info("Configured SSL/TLS for database connections")
            return True

        except (urllib.error.URLError, OSError, ClientError) as e:
            logger.error("Failed to setup SSL/TLS: %s", str(e), exc_info=True)
            return False

    def create_read_replicas(self, num_replicas: int = 2) -> List[str]:
        """Create read replicas for load distribution."""
        replica_endpoints = []

        for i in range(num_replicas):
            replica_identifier = f"{self.db_identifier}-read-{i+1}"

            try:
                # Check if replica exists
                try:
                    response = self.rds_client.describe_db_instances(
                        DBInstanceIdentifier=replica_identifier
                    )
                    if response["DBInstances"]:
                        endpoint = response["DBInstances"][0]["Endpoint"]["Address"]
                        replica_endpoints.append(endpoint)
                        logger.info(
                            f"Read replica already exists: {replica_identifier}"
                        )
                        continue
                except ClientError as e:
                    if e.response["Error"]["Code"] != "DBInstanceNotFound":
                        raise

                # Create read replica
                availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
                az = availability_zones[i % len(availability_zones)]

                response = self.rds_client.create_db_instance_read_replica(
                    DBInstanceIdentifier=replica_identifier,
                    SourceDBInstanceIdentifier=self.db_identifier,
                    DBInstanceClass=self.db_instance_class,
                    AvailabilityZone=az,
                    PubliclyAccessible=False,
                    MultiAZ=False,  # Read replicas don't need Multi-AZ
                    StorageEncrypted=True,
                    EnablePerformanceInsights=True,
                    MonitoringInterval=60,
                    MonitoringRoleArn=self._create_monitoring_role(),
                    EnableCloudwatchLogsExports=["postgresql"],
                    Tags=[
                        {"Key": "Project", "Value": "HavenHealth"},
                        {"Key": "Type", "Value": "ReadReplica"},
                    ],
                )

                # Wait for replica to be available
                logger.info(f"Creating read replica: {replica_identifier}")
                waiter = self.rds_client.get_waiter("db_instance_available")
                waiter.wait(DBInstanceIdentifier=replica_identifier)

                # Get endpoint
                response = self.rds_client.describe_db_instances(
                    DBInstanceIdentifier=replica_identifier
                )
                endpoint = response["DBInstances"][0]["Endpoint"]["Address"]
                replica_endpoints.append(endpoint)

                logger.info(f"Created read replica: {endpoint}")

            except ClientError as e:
                logger.error(f"Failed to create read replica {replica_identifier}: {e}")

        return replica_endpoints

    def setup_monitoring_alerts(self) -> bool:
        """Implement CloudWatch monitoring and alerts."""
        try:
            # Create SNS topic for alerts
            sns_client = boto3.client("sns", region_name=self.region)

            topic_name = "haven-health-db-alerts"
            try:
                response = sns_client.create_topic(Name=topic_name)
                topic_arn = response["TopicArn"]
            except ClientError:
                # Get existing topic
                response = sns_client.list_topics()
                topic_arn = next(
                    t["TopicArn"]
                    for t in response["Topics"]
                    if topic_name in t["TopicArn"]
                )

            # Subscribe email for alerts
            if hasattr(settings, "alert_email"):
                sns_client.subscribe(
                    TopicArn=topic_arn, Protocol="email", Endpoint=settings.alert_email
                )

            # Create CloudWatch alarms
            alarms = [
                {
                    "AlarmName": f"{self.db_identifier}-cpu-high",
                    "MetricName": "CPUUtilization",
                    "Statistic": "Average",
                    "Period": 300,
                    "EvaluationPeriods": 2,
                    "Threshold": 80,
                    "ComparisonOperator": "GreaterThanThreshold",
                    "AlarmDescription": "RDS CPU utilization above 80%",
                },
                {
                    "AlarmName": f"{self.db_identifier}-connections-high",
                    "MetricName": "DatabaseConnections",
                    "Statistic": "Average",
                    "Period": 300,
                    "EvaluationPeriods": 2,
                    "Threshold": 160,  # 80% of max_connections
                    "ComparisonOperator": "GreaterThanThreshold",
                    "AlarmDescription": "RDS connections above 80% of maximum",
                },
                {
                    "AlarmName": f"{self.db_identifier}-storage-low",
                    "MetricName": "FreeStorageSpace",
                    "Statistic": "Average",
                    "Period": 300,
                    "EvaluationPeriods": 1,
                    "Threshold": 10737418240,  # 10GB in bytes
                    "ComparisonOperator": "LessThanThreshold",
                    "AlarmDescription": "RDS free storage below 10GB",
                },
                {
                    "AlarmName": f"{self.db_identifier}-read-latency-high",
                    "MetricName": "ReadLatency",
                    "Statistic": "Average",
                    "Period": 300,
                    "EvaluationPeriods": 2,
                    "Threshold": 0.05,  # 50ms
                    "ComparisonOperator": "GreaterThanThreshold",
                    "AlarmDescription": "RDS read latency above 50ms",
                },
                {
                    "AlarmName": f"{self.db_identifier}-write-latency-high",
                    "MetricName": "WriteLatency",
                    "Statistic": "Average",
                    "Period": 300,
                    "EvaluationPeriods": 2,
                    "Threshold": 0.1,  # 100ms
                    "ComparisonOperator": "GreaterThanThreshold",
                    "AlarmDescription": "RDS write latency above 100ms",
                },
                {
                    "AlarmName": f"{self.db_identifier}-deadlocks",
                    "MetricName": "Deadlocks",
                    "Statistic": "Sum",
                    "Period": 300,
                    "EvaluationPeriods": 1,
                    "Threshold": 5,
                    "ComparisonOperator": "GreaterThanThreshold",
                    "AlarmDescription": "RDS deadlocks detected",
                },
            ]

            for alarm in alarms:
                self.cloudwatch_client.put_metric_alarm(
                    AlarmName=alarm["AlarmName"],
                    ComparisonOperator=alarm["ComparisonOperator"],
                    EvaluationPeriods=alarm["EvaluationPeriods"],
                    MetricName=alarm["MetricName"],
                    Namespace="AWS/RDS",
                    Period=alarm["Period"],
                    Statistic=alarm["Statistic"],
                    Threshold=alarm["Threshold"],
                    ActionsEnabled=True,
                    AlarmActions=[topic_arn],
                    AlarmDescription=alarm["AlarmDescription"],
                    Dimensions=[
                        {"Name": "DBInstanceIdentifier", "Value": self.db_identifier}
                    ],
                )

            logger.info("Set up monitoring alerts")
            return True

        except ClientError as e:
            logger.error(f"Failed to setup monitoring alerts: {e}")
            return False

    def initialize_complete_infrastructure(self) -> Dict[str, Any]:
        """Initialize complete database infrastructure."""
        results: Dict[str, Any] = {}

        # Set up RDS instance
        endpoint = self.setup_postgresql_rds()
        results["rds_endpoint"] = endpoint
        results["rds_setup"] = bool(endpoint)

        # Configure connection pooling
        if endpoint:
            engine = self.configure_connection_pool()
            results["connection_pool"] = engine is not None

        # Set up automated backups
        results["automated_backups"] = self.setup_automated_backups()

        # Enable point-in-time recovery
        results["point_in_time_recovery"] = self.enable_point_in_time_recovery()

        # Configure SSL/TLS
        results["ssl_tls"] = self.setup_ssl_tls()

        # Create read replicas
        replica_endpoints = self.create_read_replicas()
        results["read_replicas"] = replica_endpoints
        results["read_replicas_created"] = len(replica_endpoints) > 0

        # Set up monitoring alerts
        results["monitoring_alerts"] = self.setup_monitoring_alerts()

        # Summary
        success_count = sum(
            1
            for k, v in results.items()
            if k.endswith("_setup")
            or k.endswith("_created")
            or k
            in [
                "automated_backups",
                "point_in_time_recovery",
                "ssl_tls",
                "monitoring_alerts",
            ]
            and v
        )
        total_count = 7  # Total infrastructure components

        logger.info(
            f"Database infrastructure initialization complete: {success_count}/{total_count} successful"
        )

        return results


# Create singleton instance
db_infrastructure = DatabaseInfrastructure()
