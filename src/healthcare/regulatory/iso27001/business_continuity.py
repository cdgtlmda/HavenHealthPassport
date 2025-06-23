"""ISO 27001/22301 Business Continuity Management for Healthcare.

This module implements a comprehensive business continuity management system aligned
with ISO 27001:2022 and ISO 22301:2019 requirements, specifically tailored for
healthcare organizations to ensure continuous patient care and data availability.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, cast
from uuid import uuid4

from src.healthcare.fhir_validator import FHIRValidator
from src.security.encryption import EncryptionService

logger = logging.getLogger(__name__)


class CriticalityLevel(Enum):
    """Business process criticality levels."""

    CRITICAL = (1, "critical", "Life-threatening if unavailable", 0)  # RTO in hours
    HIGH = (2, "high", "Significant patient/operational impact", 4)
    MEDIUM = (3, "medium", "Moderate impact on operations", 24)
    LOW = (4, "low", "Minor inconvenience", 72)

    def __init__(
        self, level: int, level_name: str, description: str, max_rto_hours: int
    ):
        """Initialize criticality level with recovery time objective."""
        self.level = level
        self.level_name = level_name
        self.description = description
        self.max_rto_hours = max_rto_hours


class DisruptionType(Enum):
    """Types of business disruptions."""

    # Natural disasters
    NATURAL_DISASTER = "natural_disaster"
    PANDEMIC = "pandemic"
    SEVERE_WEATHER = "severe_weather"

    # Technical failures
    SYSTEM_FAILURE = "system_failure"
    CYBER_ATTACK = "cyber_attack"
    POWER_OUTAGE = "power_outage"
    NETWORK_FAILURE = "network_failure"

    # Human factors
    STAFF_SHORTAGE = "staff_shortage"
    STRIKE = "strike"
    KEY_PERSON_LOSS = "key_person_loss"

    # External factors
    SUPPLIER_FAILURE = "supplier_failure"
    REGULATORY_SHUTDOWN = "regulatory_shutdown"
    FACILITY_DAMAGE = "facility_damage"

    # Healthcare-specific
    MEDICAL_EQUIPMENT_FAILURE = "medical_equipment_failure"
    PHARMACEUTICAL_SHORTAGE = "pharmaceutical_shortage"
    CONTAMINATION = "contamination_event"


class RecoveryStrategy(Enum):
    """Business continuity recovery strategies."""

    HOT_SITE = "hot_site"  # Fully equipped duplicate facility
    WARM_SITE = "warm_site"  # Partially equipped backup facility
    COLD_SITE = "cold_site"  # Basic facility, no equipment
    CLOUD_RECOVERY = "cloud_recovery"  # Cloud-based recovery
    MOBILE_RECOVERY = "mobile_recovery"  # Mobile units
    RECIPROCAL = "reciprocal_agreement"  # Agreement with partner org
    MANUAL_WORKAROUND = "manual_workaround"  # Paper-based processes
    WORK_FROM_HOME = "work_from_home"  # Remote work arrangement


class TestType(Enum):
    """Types of continuity tests."""

    TABLETOP = "tabletop_exercise"
    WALKTHROUGH = "walkthrough_test"
    SIMULATION = "simulation"
    PARALLEL = "parallel_test"
    FULL_INTERRUPTION = "full_interruption_test"


class BusinessProcess:
    """Represents a business process for continuity planning."""

    def __init__(
        self,
        process_id: str,
        name: str,
        department: str,
        description: str,
        criticality: CriticalityLevel,
        owner: str,
    ):
        """Initialize business process.

        Args:
            process_id: Unique process ID
            name: Process name
            department: Department owning process
            description: Process description
            criticality: Criticality level
            owner: Process owner
        """
        self.process_id = process_id
        self.name = name
        self.department = department
        self.description = description
        self.criticality = criticality
        self.owner = owner

        # Recovery objectives
        self.rto = criticality.max_rto_hours  # Recovery Time Objective (hours)
        self.rpo = (
            4 if criticality.level <= 2 else 24
        )  # Recovery Point Objective (hours)
        self.mtpd = (
            criticality.max_rto_hours * 2
        )  # Maximum Tolerable Period of Disruption

        # Dependencies
        self.it_dependencies: List[Dict[str, Any]] = []
        self.process_dependencies: List[str] = []
        self.resource_requirements: Dict[str, Any] = {}
        self.minimum_staff: int = 1

        # Healthcare-specific
        self.patient_facing: bool = False
        self.clinical_process: bool = False
        self.regulatory_required: bool = False
        self.phi_processing: bool = False  # PHI data must be encrypted

        # Recovery details
        self.recovery_strategy: Optional[RecoveryStrategy] = None
        self.recovery_procedures: List[str] = []
        self.alternate_procedures: List[str] = []

        # Encryption service for PHI data
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

    def add_it_dependency(self, system: str, criticality: str) -> None:
        """Add IT system dependency.

        Args:
            system: System name
            criticality: Dependency criticality
        """
        self.it_dependencies.append(
            {"system": system, "criticality": criticality, "added_date": datetime.now()}
        )

    def set_recovery_requirements(
        self,
        rto_hours: int,
        rpo_hours: int,
        minimum_staff: int,
        resources: Dict[str, Any],
    ) -> None:
        """Set recovery requirements.

        Args:
            rto_hours: Recovery Time Objective
            rpo_hours: Recovery Point Objective
            minimum_staff: Minimum staff required
            resources: Resource requirements
        """
        self.rto = rto_hours
        self.rpo = rpo_hours
        self.minimum_staff = minimum_staff
        self.resource_requirements = resources
        self.mtpd = rto_hours * 2  # Default MTPD calculation


class BusinessContinuityPlan:
    """Business continuity plan for specific scenarios."""

    def __init__(
        self,
        plan_id: str,
        name: str,
        scenario: DisruptionType,
        scope: List[str],  # Process IDs covered
        owner: str,
    ):
        """Initialize business continuity plan.

        Args:
            plan_id: Unique plan ID
            name: Plan name
            scenario: Disruption scenario
            scope: Processes covered
            owner: Plan owner
        """
        self.plan_id = plan_id
        self.name = name
        self.scenario = scenario
        self.scope = scope
        self.owner = owner
        self.created_date = datetime.now()
        self.last_updated = datetime.now()
        self.version = "1.0"

        # Plan components
        self.activation_criteria: List[Dict[str, Any]] = []
        self.notification_list: List[Dict[str, str]] = []
        self.response_teams: Dict[str, List[Dict[str, Any]]] = {}
        self.immediate_actions: List[Dict[str, Any]] = []
        self.recovery_procedures: List[Dict[str, Any]] = []
        self.communication_plan: Dict[str, Any] = {}

        # Healthcare-specific
        self.clinical_protocols: List[Dict[str, Any]] = []
        self.patient_communication: Dict[str, Any] = {}
        self.regulatory_notifications: List[Dict[str, Any]] = []
        self.medical_supply_alternatives: Dict[str, List[str]] = {}

        # Testing
        self.test_history: List[Dict[str, Any]] = []
        self.last_test_date: Optional[datetime] = None
        self.next_test_date: Optional[datetime] = None

    def add_activation_trigger(self, trigger: str, threshold: Any) -> None:
        """Add plan activation trigger.

        Args:
            trigger: Trigger description
            threshold: Activation threshold
        """
        self.activation_criteria.append(
            {"trigger": trigger, "threshold": threshold, "added_date": datetime.now()}
        )

    def add_team_member(self, team: str, member: str, role: str, contact: str) -> None:
        """Add response team member.

        Args:
            team: Team name
            member: Member name
            role: Member role
            contact: Contact information
        """
        if team not in self.response_teams:
            self.response_teams[team] = []

        self.response_teams[team].append(
            {
                "name": member,
                "role": role,
                "contact": contact,
                "primary": len(self.response_teams[team]) == 0,
            }
        )

    def record_test(
        self,
        test_type: TestType,
        test_date: datetime,
        participants: List[str],
        results: Dict[str, Any],
    ) -> None:
        """Record plan test.

        Args:
            test_type: Type of test
            test_date: Test date
            participants: Test participants
            results: Test results
        """
        self.test_history.append(
            {
                "test_id": f"TEST-{uuid4().hex[:8]}",
                "type": test_type.value,
                "date": test_date,
                "participants": participants,
                "results": results,
                "lessons_learned": results.get("lessons_learned", []),
            }
        )

        self.last_test_date = test_date
        self.next_test_date = test_date + timedelta(days=180)  # 6 months


class BusinessContinuityFramework:
    """ISO 27001/22301 Business Continuity Framework for Healthcare."""

    # FHIR resource type
    __fhir_resource__ = "AuditEvent"

    def __init__(self) -> None:
        """Initialize business continuity framework."""
        self.processes: Dict[str, BusinessProcess] = {}
        self.plans: Dict[str, BusinessContinuityPlan] = {}
        self.impact_analyses: List[Dict[str, Any]] = []
        self.recovery_sites: Dict[str, Dict[str, Any]] = {}
        self.test_schedule: List[Dict[str, Any]] = []
        self.incidents: List[Dict[str, Any]] = []
        self.metrics: Dict[str, Any] = {
            "processes_identified": 0,
            "plans_created": 0,
            "tests_conducted": 0,
            "successful_recoveries": 0,
        }

        # Initialize healthcare-specific components
        self._initialize_healthcare_continuity()

        # Add FHIR validator
        self.fhir_validator = FHIRValidator()

    def _initialize_healthcare_continuity(self) -> None:
        """Initialize healthcare-specific continuity components."""
        # Clinical continuity templates
        self.clinical_protocols = {
            "emergency_care": {
                "priority": "critical",
                "max_downtime": "0 hours",
                "backup_procedures": ["Paper charts", "Verbal orders", "Manual vitals"],
            },
            "patient_records": {
                "priority": "high",
                "max_downtime": "4 hours",
                "backup_procedures": [
                    "Read-only access",
                    "Printed summaries",
                    "Phone verification",
                ],
            },
            "pharmacy": {
                "priority": "high",
                "max_downtime": "2 hours",
                "backup_procedures": [
                    "Manual dispensing",
                    "Paper prescriptions",
                    "Emergency stock",
                ],
            },
            "laboratory": {
                "priority": "high",
                "max_downtime": "4 hours",
                "backup_procedures": [
                    "External lab",
                    "Point-of-care testing",
                    "Manual reporting",
                ],
            },
            "imaging": {
                "priority": "medium",
                "max_downtime": "8 hours",
                "backup_procedures": [
                    "Portable units",
                    "External facilities",
                    "Film backup",
                ],
            },
        }

        # Regulatory requirements
        self.regulatory_requirements = {
            "cms_conditions": {
                "emergency_preparedness": True,
                "testing_frequency": "annual",
                "documentation_required": True,
            },
            "joint_commission": {
                "emergency_management": True,
                "96_hour_sustainability": True,
                "hazard_vulnerability_analysis": True,
            },
            "hipaa": {
                "data_backup": True,
                "disaster_recovery": True,
                "emergency_access": True,
            },
        }

    def register_business_process(
        self,
        name: str,
        department: str,
        description: str,
        criticality: CriticalityLevel,
        owner: str,
        healthcare_attributes: Optional[Dict[str, bool]] = None,
    ) -> str:
        """Register business process for continuity planning.

        Args:
            name: Process name
            department: Department
            description: Process description
            criticality: Criticality level
            owner: Process owner
            healthcare_attributes: Healthcare-specific attributes

        Returns:
            Process ID
        """
        process_id = f"PROC-{uuid4().hex[:8]}"

        process = BusinessProcess(
            process_id=process_id,
            name=name,
            department=department,
            description=description,
            criticality=criticality,
            owner=owner,
        )

        # Set healthcare attributes
        if healthcare_attributes:
            process.patient_facing = healthcare_attributes.get("patient_facing", False)
            process.clinical_process = healthcare_attributes.get(
                "clinical_process", False
            )
            process.regulatory_required = healthcare_attributes.get(
                "regulatory_required", False
            )
            process.phi_processing = healthcare_attributes.get("phi_processing", False)

        self.processes[process_id] = process
        self.metrics["processes_identified"] += 1

        logger.info("Registered business process: %s - %s", process_id, name)

        return process_id

    def conduct_business_impact_analysis(
        self, analyst: str, scope: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Conduct business impact analysis.

        Args:
            analyst: Person conducting analysis
            scope: Specific processes to analyze (None for all)

        Returns:
            BIA results
        """
        bia_id = f"BIA-{uuid4().hex[:8]}"

        # Select processes to analyze
        if scope:
            target_processes = {
                pid: p for pid, p in self.processes.items() if pid in scope
            }
        else:
            target_processes = self.processes

        bia_results: Dict[str, Any] = {
            "bia_id": bia_id,
            "analyst": analyst,
            "analysis_date": datetime.now(),
            "scope": len(target_processes),
            "critical_processes": [],
            "dependencies_map": {},
            "resource_requirements": {},
            "recovery_priorities": [],
            "total_risk_exposure": 0,
        }

        # Analyze each process
        for process_id, process in target_processes.items():
            impact_score = self._calculate_process_impact(process)

            process_analysis = {
                "process_id": process_id,
                "name": process.name,
                "criticality": process.criticality.name,
                "impact_score": impact_score,
                "rto": process.rto,
                "rpo": process.rpo,
                "dependencies": {
                    "it_systems": len(process.it_dependencies),
                    "other_processes": len(process.process_dependencies),
                    "minimum_staff": process.minimum_staff,
                },
                "healthcare_impact": {
                    "patient_facing": process.patient_facing,
                    "clinical_process": process.clinical_process,
                    "phi_processing": process.phi_processing,
                },
            }

            # Categorize by criticality
            if process.criticality == CriticalityLevel.CRITICAL:
                bia_results["critical_processes"].append(process_analysis)

            # Map dependencies
            bia_results["dependencies_map"][process_id] = {
                "depends_on": process.it_dependencies + process.process_dependencies,
                "depended_by": [],  # Would be populated by reverse lookup
            }

            # Aggregate resource requirements
            for resource, quantity in process.resource_requirements.items():
                if resource not in bia_results["resource_requirements"]:
                    bia_results["resource_requirements"][resource] = 0
                bia_results["resource_requirements"][resource] += quantity

            # Add to recovery priorities
            bia_results["recovery_priorities"].append(
                {
                    "process_id": process_id,
                    "priority": process.criticality.level,
                    "rto": process.rto,
                }
            )

        # Sort recovery priorities
        bia_results["recovery_priorities"].sort(key=lambda x: (x["priority"], x["rto"]))

        # Calculate total risk exposure
        bia_results["total_risk_exposure"] = sum(
            self._calculate_process_impact(p) for p in target_processes.values()
        )

        # Generate recommendations
        bia_results["recommendations"] = self._generate_bia_recommendations(bia_results)

        # Store analysis
        self.impact_analyses.append(bia_results)

        logger.info(
            "Completed BIA %s: %d processes analyzed", bia_id, len(target_processes)
        )

        return bia_results

    def create_continuity_plan(
        self,
        name: str,
        scenario: DisruptionType,
        process_ids: List[str],
        owner: str,
        healthcare_specific: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create business continuity plan.

        Args:
            name: Plan name
            scenario: Disruption scenario
            process_ids: Processes covered
            owner: Plan owner
            healthcare_specific: Healthcare-specific components

        Returns:
            Plan ID
        """
        plan_id = f"BCP-{uuid4().hex[:8]}"

        plan = BusinessContinuityPlan(
            plan_id=plan_id,
            name=name,
            scenario=scenario,
            scope=process_ids,
            owner=owner,
        )

        # Add standard activation criteria
        if scenario == DisruptionType.SYSTEM_FAILURE:
            plan.add_activation_trigger("Critical system unavailable", "> 30 minutes")
            plan.add_activation_trigger("Data center inaccessible", "confirmed")
        elif scenario == DisruptionType.NATURAL_DISASTER:
            plan.add_activation_trigger(
                "Facility evacuation ordered", "official notice"
            )
            plan.add_activation_trigger("Staff availability", "< 50%")
        elif scenario == DisruptionType.CYBER_ATTACK:
            plan.add_activation_trigger("Ransomware detected", "confirmed")
            plan.add_activation_trigger("Data breach", "> 500 records")

        # Add healthcare-specific components
        if healthcare_specific:
            if "clinical_protocols" in healthcare_specific:
                plan.clinical_protocols = healthcare_specific["clinical_protocols"]
            if "patient_communication" in healthcare_specific:
                plan.patient_communication = healthcare_specific[
                    "patient_communication"
                ]
            if "medical_supplies" in healthcare_specific:
                plan.medical_supply_alternatives = healthcare_specific[
                    "medical_supplies"
                ]

        # Create initial teams
        plan.response_teams = {
            "Crisis Management Team": [],
            "Operations Team": [],
            "Communications Team": [],
            "IT Recovery Team": [],
        }

        if any(
            self.processes[pid].clinical_process
            for pid in process_ids
            if pid in self.processes
        ):
            plan.response_teams["Clinical Continuity Team"] = []

        # Add immediate actions based on scenario
        plan.immediate_actions = self._generate_immediate_actions(scenario, process_ids)

        # Add recovery procedures
        plan.recovery_procedures = self._generate_recovery_procedures(
            scenario, process_ids
        )

        # Store plan
        self.plans[plan_id] = plan
        self.metrics["plans_created"] += 1

        logger.info("Created continuity plan: %s - %s", plan_id, name)

        return plan_id

    def define_recovery_strategy(
        self,
        process_id: str,
        strategy: RecoveryStrategy,
        implementation_details: Dict[str, Any],
    ) -> bool:
        """Define recovery strategy for process.

        Args:
            process_id: Process ID
            strategy: Recovery strategy
            implementation_details: Implementation details

        Returns:
            Success status
        """
        process = self.processes.get(process_id)
        if not process:
            return False

        process.recovery_strategy = strategy

        # Add strategy-specific procedures
        if strategy == RecoveryStrategy.HOT_SITE:
            process.recovery_procedures = [
                "Activate hot site",
                "Redirect network traffic",
                "Synchronize data",
                "Verify system functionality",
                "Switch user access",
            ]
        elif strategy == RecoveryStrategy.CLOUD_RECOVERY:
            process.recovery_procedures = [
                "Activate cloud instances",
                "Restore from cloud backup",
                "Configure network access",
                "Verify data integrity",
                "Enable user access",
            ]
        elif strategy == RecoveryStrategy.MANUAL_WORKAROUND:
            process.recovery_procedures = [
                "Distribute paper forms",
                "Activate manual procedures",
                "Brief staff on protocols",
                "Establish paper workflow",
                "Plan data re-entry",
            ]

        # Add healthcare-specific procedures
        if process.clinical_process:
            process.recovery_procedures.extend(
                [
                    "Ensure patient safety protocols",
                    "Maintain treatment continuity",
                    "Document manually if needed",
                ]
            )

        # Store implementation details
        process.resource_requirements.update(implementation_details)

        logger.info("Defined recovery strategy for %s: %s", process_id, strategy.value)

        return True

    def register_recovery_site(
        self,
        site_name: str,
        site_type: RecoveryStrategy,
        location: str,
        capabilities: Dict[str, Any],
        contact_info: Dict[str, str],
    ) -> str:
        """Register recovery site.

        Args:
            site_name: Site name
            site_type: Type of recovery site
            location: Site location
            capabilities: Site capabilities
            contact_info: Contact information

        Returns:
            Site ID
        """
        site_id = f"SITE-{uuid4().hex[:8]}"

        site = {
            "site_id": site_id,
            "name": site_name,
            "type": site_type.value,
            "location": location,
            "capabilities": capabilities,
            "contact_info": contact_info,
            "status": "available",
            "last_tested": None,
            "assigned_processes": [],
            "activation_time": capabilities.get("activation_time", "4 hours"),
            "capacity": capabilities.get("capacity", {}),
            "healthcare_certified": capabilities.get("healthcare_certified", False),
        }

        self.recovery_sites[site_id] = site

        logger.info("Registered recovery site: %s - %s", site_id, site_name)

        return site_id

    def schedule_continuity_test(
        self,
        plan_id: str,
        test_type: TestType,
        test_date: datetime,
        participants: List[str],
        objectives: List[str],
    ) -> str:
        """Schedule continuity test.

        Args:
            plan_id: Plan to test
            test_type: Type of test
            test_date: Test date
            participants: Test participants
            objectives: Test objectives

        Returns:
            Test ID
        """
        test_id = f"BCT-{uuid4().hex[:8]}"

        test = {
            "test_id": test_id,
            "plan_id": plan_id,
            "test_type": test_type.value,
            "scheduled_date": test_date,
            "participants": participants,
            "objectives": objectives,
            "status": "scheduled",
            "scenarios": [],
            "success_criteria": [],
            "resources_required": [],
        }

        # Add test type specific elements
        if test_type == TestType.TABLETOP:
            test["duration"] = "2 hours"
            test["location"] = "Conference room"
        elif test_type == TestType.SIMULATION:
            test["duration"] = "4 hours"
            test["systems_involved"] = []
        elif test_type == TestType.FULL_INTERRUPTION:
            test["duration"] = "8 hours"
            test["safety_protocols"] = []
            test["rollback_plan"] = []

        # Add healthcare-specific test elements
        plan = self.plans.get(plan_id)
        if plan and any(
            self.processes.get(pid) and self.processes[pid].clinical_process
            for pid in plan.scope
            if pid in self.processes
        ):
            test["clinical_safety_measures"] = [
                "Ensure patient care continuity",
                "Medical staff on standby",
                "Emergency protocols active",
            ]

        self.test_schedule.append(test)

        logger.info("Scheduled continuity test: %s for %s", test_id, test_date)

        return test_id

    def execute_continuity_test(
        self, test_id: str, actual_participants: List[str], test_results: Dict[str, Any]
    ) -> bool:
        """Execute scheduled continuity test.

        Args:
            test_id: Test ID
            actual_participants: Actual participants
            test_results: Test results

        Returns:
            Success status
        """
        # Find test
        test = None
        for scheduled_test in self.test_schedule:
            if scheduled_test["test_id"] == test_id:
                test = scheduled_test
                break

        if not test:
            return False

        # Update test record
        test["status"] = "completed"
        test["actual_participants"] = actual_participants
        test["execution_date"] = datetime.now()
        test["results"] = test_results

        # Calculate test metrics
        test["metrics"] = {
            "objectives_met": test_results.get("objectives_met", 0),
            "total_objectives": len(test["objectives"]),
            "issues_identified": len(test_results.get("issues", [])),
            "participant_attendance": len(actual_participants)
            / len(test["participants"]),
        }

        # Update plan test history
        plan = self.plans.get(test["plan_id"])
        if plan:
            plan.record_test(
                test_type=TestType(test["test_type"]),
                test_date=datetime.now(),
                participants=actual_participants,
                results=test_results,
            )

        self.metrics["tests_conducted"] += 1

        logger.info("Completed continuity test: %s", test_id)

        return True

    def activate_continuity_plan(
        self,
        plan_id: str,
        incident_description: str,
        activated_by: str,
        affected_processes: List[str],
    ) -> str:
        """Activate business continuity plan.

        Args:
            plan_id: Plan to activate
            incident_description: Incident description
            activated_by: Person activating plan
            affected_processes: Affected processes

        Returns:
            Activation ID
        """
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        activation_id = f"ACT-{uuid4().hex[:8]}"

        activation: Dict[str, Any] = {
            "activation_id": activation_id,
            "plan_id": plan_id,
            "incident_description": incident_description,
            "activated_by": activated_by,
            "activation_time": datetime.now(),
            "affected_processes": affected_processes,
            "status": "active",
            "actions_taken": [],
            "resources_deployed": [],
            "recovery_progress": {},
        }

        # Execute immediate actions
        for action in plan.immediate_actions:
            activation["actions_taken"].append(
                {"action": action, "executed_at": datetime.now(), "status": "initiated"}
            )

        # Notify response teams
        notifications_sent = self._send_activation_notifications(plan, activation)
        activation["notifications_sent"] = notifications_sent

        # Track activation
        self.incidents.append(activation)

        logger.warning("CONTINUITY PLAN ACTIVATED: %s (%s)", plan.name, activation_id)

        return activation_id

    def update_recovery_progress(
        self,
        activation_id: str,
        process_id: str,
        status: str,
        percentage_complete: int,
        updated_by: str,
    ) -> bool:
        """Update recovery progress for activated plan.

        Args:
            activation_id: Activation ID
            process_id: Process being recovered
            status: Recovery status
            percentage_complete: Completion percentage
            updated_by: Person updating

        Returns:
            Success status
        """
        # Find activation
        activation = None
        for incident in self.incidents:
            if incident["activation_id"] == activation_id:
                activation = incident
                break

        if not activation:
            return False

        # Update progress
        if process_id not in activation["recovery_progress"]:
            activation["recovery_progress"][process_id] = []

        activation["recovery_progress"][process_id].append(
            {
                "timestamp": datetime.now(),
                "status": status,
                "percentage_complete": percentage_complete,
                "updated_by": updated_by,
            }
        )

        # Check if all processes recovered
        all_recovered = all(
            progress[-1]["percentage_complete"] == 100
            for process_id, progress in activation["recovery_progress"].items()
            if progress and process_id in activation["affected_processes"]
        )

        if all_recovered:
            activation["status"] = "recovered"
            activation["recovery_time"] = datetime.now()
            self.metrics["successful_recoveries"] += 1

        logger.info(
            "Recovery progress updated for %s: %d%% complete",
            process_id,
            percentage_complete,
        )

        return True

    def generate_continuity_report(
        self, report_type: str = "executive"
    ) -> Dict[str, Any]:
        """Generate business continuity report.

        Args:
            report_type: Type of report

        Returns:
            Continuity report
        """
        report = {
            "report_id": f"BCM-RPT-{uuid4().hex[:8]}",
            "generated_date": datetime.now(),
            "report_type": report_type,
            "summary": {
                "total_processes": len(self.processes),
                "critical_processes": len(
                    [
                        p
                        for p in self.processes.values()
                        if p.criticality == CriticalityLevel.CRITICAL
                    ]
                ),
                "plans_created": len(self.plans),
                "tests_conducted": self.metrics["tests_conducted"],
                "activations": len(self.incidents),
            },
            "readiness_assessment": self._assess_continuity_readiness(),
            "test_compliance": self._check_test_compliance(),
            "recovery_capabilities": self._assess_recovery_capabilities(),
        }

        if report_type == "detailed":
            report["process_analysis"] = {
                "by_criticality": self._analyze_processes_by_criticality(),
                "by_department": self._analyze_processes_by_department(),
                "dependency_analysis": self._analyze_dependencies(),
            }
            report["plan_coverage"] = self._analyze_plan_coverage()

        elif report_type == "healthcare":
            report["clinical_continuity"] = self._analyze_clinical_continuity()
            report["regulatory_compliance"] = self._check_regulatory_compliance()
            report["patient_impact_analysis"] = self._analyze_patient_impact()

        return report

    def _calculate_process_impact(self, process: BusinessProcess) -> int:
        """Calculate process impact score.

        Args:
            process: Business process

        Returns:
            Impact score
        """
        base_score = float(process.criticality.level * 100)

        # Healthcare modifiers
        if process.patient_facing:
            base_score *= 1.5
        if process.clinical_process:
            base_score *= 2.0
        if process.regulatory_required:
            base_score *= 1.3
        if process.phi_processing:
            base_score *= 1.2

        # Dependency modifiers
        base_score += len(process.it_dependencies) * 10
        base_score += len(process.process_dependencies) * 15

        return int(base_score)

    def _generate_bia_recommendations(
        self, bia_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate BIA recommendations.

        Args:
            bia_results: BIA results

        Returns:
            Recommendations
        """
        recommendations: List[Dict[str, Any]] = []

        # Check for critical processes without plans
        critical_without_plans = []
        for proc in bia_results["critical_processes"]:
            has_plan = any(
                proc["process_id"] in plan.scope for plan in self.plans.values()
            )
            if not has_plan:
                critical_without_plans.append(proc["name"])

        if critical_without_plans:
            recommendations.append(
                {
                    "priority": "high",
                    "recommendation": "Create continuity plans for critical processes",
                    "affected_processes": critical_without_plans[:5],
                }
            )

        # Check for single points of failure
        spof_count = sum(
            1
            for deps in bia_results["dependencies_map"].values()
            if len(deps["depends_on"]) > 3
        )

        if spof_count > 0:
            recommendations.append(
                {
                    "priority": "medium",
                    "recommendation": "Address single points of failure",
                    "count": spof_count,
                    "mitigation": "Implement redundancy or alternate procedures",
                }
            )

        # Resource constraints
        if len(bia_results["resource_requirements"]) > 0:
            recommendations.append(
                {
                    "priority": "medium",
                    "recommendation": "Ensure resource availability for recovery",
                    "key_resources": list(bia_results["resource_requirements"].keys())[
                        :5
                    ],
                }
            )

        return recommendations

    def _generate_immediate_actions(
        self, scenario: DisruptionType, process_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate immediate actions for scenario.

        Args:
            scenario: Disruption scenario
            process_ids: Affected processes

        Returns:
            Immediate actions
        """
        actions = []

        # Common immediate actions
        actions.extend(
            [
                {
                    "action": "Activate crisis management team",
                    "timeframe": "Immediate",
                    "responsible": "On-call manager",
                },
                {
                    "action": "Assess scope of disruption",
                    "timeframe": "15 minutes",
                    "responsible": "Operations team",
                },
                {
                    "action": "Initiate staff notification",
                    "timeframe": "30 minutes",
                    "responsible": "HR/Communications",
                },
            ]
        )

        # Scenario-specific actions
        if scenario == DisruptionType.CYBER_ATTACK:
            actions.extend(
                [
                    {
                        "action": "Isolate affected systems",
                        "timeframe": "Immediate",
                        "responsible": "IT Security",
                    },
                    {
                        "action": "Preserve forensic evidence",
                        "timeframe": "Immediate",
                        "responsible": "IT Security",
                    },
                ]
            )
        elif scenario == DisruptionType.NATURAL_DISASTER:
            actions.extend(
                [
                    {
                        "action": "Ensure staff and patient safety",
                        "timeframe": "Immediate",
                        "responsible": "Facility management",
                    },
                    {
                        "action": "Activate evacuation procedures if needed",
                        "timeframe": "As required",
                        "responsible": "Safety officer",
                    },
                ]
            )

        # Healthcare-specific actions
        if any(
            self.processes.get(pid) and self.processes[pid].clinical_process
            for pid in process_ids
            if pid in self.processes
        ):
            actions.insert(
                0,
                {
                    "action": "Ensure patient safety and care continuity",
                    "timeframe": "Immediate",
                    "responsible": "Clinical leadership",
                },
            )

        return actions

    def _generate_recovery_procedures(
        self, scenario: DisruptionType, process_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate recovery procedures for scenario.

        Args:
            scenario: Disruption scenario
            process_ids: Affected processes

        Returns:
            Recovery procedures
        """
        procedures = []

        # Mark scenario as used (would be used to customize procedures)
        _ = scenario

        # Sort processes by priority
        prioritized_processes = sorted(
            [self.processes.get(pid) for pid in process_ids if pid in self.processes],
            key=lambda p: p.criticality.level if p else 999,
        )

        for process in prioritized_processes:
            if not process:
                continue

            procedure: Dict[str, Any] = {
                "process": process.name,
                "priority": process.criticality.name,
                "rto": f"{process.rto} hours",
                "steps": [],
            }

            # Add recovery steps based on strategy
            if process.recovery_strategy:
                procedure["strategy"] = process.recovery_strategy.value
                procedure["steps"].extend(process.recovery_procedures)
            else:
                # Default procedures
                procedure["steps"] = [
                    "Assess process functionality",
                    "Activate alternate procedures",
                    "Restore from backup if available",
                    "Verify data integrity",
                    "Resume operations",
                ]

            procedures.append(procedure)

        return procedures

    def _send_activation_notifications(
        self, plan: BusinessContinuityPlan, activation: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Send plan activation notifications.

        Args:
            plan: Activated plan
            activation: Activation details

        Returns:
            Notifications sent
        """
        notifications = []

        # Mark activation as used (would be used in notification content)
        _ = activation

        # Notify response teams
        for team_name, team_members in plan.response_teams.items():
            for member in team_members:
                notifications.append(
                    {
                        "recipient": member["name"],
                        "method": "Multiple (call, text, email)",
                        "message": f"BCP ACTIVATION: {plan.name}",
                        "sent_time": datetime.now(),
                        "team": team_name,
                    }
                )

        # Notify stakeholders from notification list
        for contact in plan.notification_list:
            notifications.append(
                {
                    "recipient": contact["name"],
                    "method": contact.get("method", "email"),
                    "message": f"Business continuity plan activated: {plan.name}",
                    "sent_time": datetime.now(),
                    "role": contact.get("role", "stakeholder"),
                }
            )

        return notifications

    def _assess_continuity_readiness(self) -> Dict[str, Any]:
        """Assess overall continuity readiness.

        Returns:
            Readiness assessment
        """
        total_processes = len(self.processes)

        if total_processes == 0:
            return {"readiness_score": 0, "status": "not_assessed"}

        # Calculate readiness metrics
        processes_with_plans = sum(
            1
            for p in self.processes.values()
            if any(p.process_id in plan.scope for plan in self.plans.values())
        )

        processes_with_strategies = sum(
            1 for p in self.processes.values() if p.recovery_strategy is not None
        )

        tested_plans = sum(
            1 for plan in self.plans.values() if plan.last_test_date is not None
        )

        # Calculate readiness score
        plan_coverage = (processes_with_plans / total_processes) * 100
        strategy_coverage = (processes_with_strategies / total_processes) * 100
        test_coverage = (tested_plans / len(self.plans)) * 100 if self.plans else 0

        readiness_score = (plan_coverage + strategy_coverage + test_coverage) / 3

        return {
            "readiness_score": round(readiness_score, 1),
            "plan_coverage": round(plan_coverage, 1),
            "strategy_coverage": round(strategy_coverage, 1),
            "test_coverage": round(test_coverage, 1),
            "status": self._get_readiness_status(readiness_score),
            "gaps": self._identify_readiness_gaps(),
        }

    def _get_readiness_status(self, score: float) -> str:
        """Get readiness status from score.

        Args:
            score: Readiness score

        Returns:
            Status description
        """
        if score >= 90:
            return "excellent"
        elif score >= 75:
            return "good"
        elif score >= 60:
            return "adequate"
        elif score >= 40:
            return "needs_improvement"
        else:
            return "critical"

    def _identify_readiness_gaps(self) -> List[str]:
        """Identify continuity readiness gaps.

        Returns:
            List of gaps
        """
        gaps = []

        # Check for processes without plans
        processes_without_plans = [
            p
            for p in self.processes.values()
            if not any(p.process_id in plan.scope for plan in self.plans.values())
        ]

        if processes_without_plans:
            gaps.append(
                f"{len(processes_without_plans)} processes lack continuity plans"
            )

        # Check for untested plans
        untested_plans = [p for p in self.plans.values() if p.last_test_date is None]

        if untested_plans:
            gaps.append(f"{len(untested_plans)} plans have never been tested")

        # Check for outdated tests
        outdated_tests = [
            p
            for p in self.plans.values()
            if p.last_test_date and (datetime.now() - p.last_test_date).days > 365
        ]

        if outdated_tests:
            gaps.append(f"{len(outdated_tests)} plans have outdated tests (>1 year)")

        # Check for critical processes without hot/warm sites
        critical_without_sites = [
            p
            for p in self.processes.values()
            if p.criticality == CriticalityLevel.CRITICAL
            and p.recovery_strategy
            not in [RecoveryStrategy.HOT_SITE, RecoveryStrategy.WARM_SITE]
        ]

        if critical_without_sites:
            gaps.append(
                f"{len(critical_without_sites)} critical processes lack rapid recovery capability"
            )

        return gaps

    def _check_test_compliance(self) -> Dict[str, Any]:
        """Check testing compliance.

        Returns:
            Test compliance status
        """
        current_year = datetime.now().year
        tests_this_year = [
            t
            for t in self.test_schedule
            if t["scheduled_date"].year == current_year and t["status"] == "completed"
        ]

        plans_tested_this_year = set(t["plan_id"] for t in tests_this_year)

        return {
            "tests_completed_this_year": len(tests_this_year),
            "plans_tested_this_year": len(plans_tested_this_year),
            "total_plans": len(self.plans),
            "compliance_percentage": (
                len(plans_tested_this_year) / len(self.plans) * 100 if self.plans else 0
            ),
            "regulatory_compliant": len(plans_tested_this_year) >= len(self.plans),
            "next_required_tests": self._get_next_required_tests(),
        }

    def _get_next_required_tests(self) -> List[Dict[str, Any]]:
        """Get next required tests.

        Returns:
            List of required tests
        """
        required_tests = []

        for plan in self.plans.values():
            if (
                plan.next_test_date
                and plan.next_test_date <= datetime.now() + timedelta(days=90)
            ):
                required_tests.append(
                    {
                        "plan_id": plan.plan_id,
                        "plan_name": plan.name,
                        "due_date": plan.next_test_date,
                        "days_until_due": (plan.next_test_date - datetime.now()).days,
                    }
                )

        return sorted(required_tests, key=lambda x: cast(Any, x["due_date"]))[:5]

    def _assess_recovery_capabilities(self) -> Dict[str, Any]:
        """Assess recovery capabilities.

        Returns:
            Recovery capability assessment
        """
        capabilities: Dict[str, Any] = {
            "recovery_strategies": {},
            "recovery_sites": len(self.recovery_sites),
            "average_rto": 0,
            "average_rpo": 0,
            "capability_gaps": [],
        }

        # Count strategies
        for process in self.processes.values():
            if process.recovery_strategy:
                strategy = process.recovery_strategy.value
                capabilities["recovery_strategies"][strategy] = (
                    capabilities["recovery_strategies"].get(strategy, 0) + 1
                )

        # Calculate averages
        if self.processes:
            capabilities["average_rto"] = sum(
                p.rto for p in self.processes.values()
            ) / len(self.processes)
            capabilities["average_rpo"] = sum(
                p.rpo for p in self.processes.values()
            ) / len(self.processes)

        # Identify gaps
        if not self.recovery_sites:
            capabilities["capability_gaps"].append("No recovery sites registered")

        manual_only = sum(
            1
            for p in self.processes.values()
            if p.recovery_strategy == RecoveryStrategy.MANUAL_WORKAROUND
        )

        if manual_only > len(self.processes) * 0.5:
            capabilities["capability_gaps"].append(
                "Over-reliance on manual workarounds"
            )

        return capabilities

    def _analyze_processes_by_criticality(self) -> Dict[str, int]:
        """Analyze processes by criticality.

        Returns:
            Process count by criticality
        """
        analysis = {}

        for criticality in CriticalityLevel:
            count = sum(
                1 for p in self.processes.values() if p.criticality == criticality
            )
            analysis[criticality.name] = count

        return analysis

    def _analyze_processes_by_department(self) -> Dict[str, int]:
        """Analyze processes by department.

        Returns:
            Process count by department
        """
        analysis: Dict[str, int] = {}

        for process in self.processes.values():
            dept = process.department
            analysis[dept] = analysis.get(dept, 0) + 1

        return analysis

    def _analyze_dependencies(self) -> Dict[str, Any]:
        """Analyze process dependencies.

        Returns:
            Dependency analysis
        """
        total_it_deps = sum(len(p.it_dependencies) for p in self.processes.values())
        total_process_deps = sum(
            len(p.process_dependencies) for p in self.processes.values()
        )

        # Find most critical dependencies
        dependency_count: Dict[str, int] = {}
        for process in self.processes.values():
            for dep in process.it_dependencies:
                system = dep["system"]
                dependency_count[system] = dependency_count.get(system, 0) + 1

        critical_dependencies = sorted(
            dependency_count.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "total_it_dependencies": total_it_deps,
            "total_process_dependencies": total_process_deps,
            "average_dependencies_per_process": (
                (total_it_deps + total_process_deps) / len(self.processes)
                if self.processes
                else 0
            ),
            "critical_dependencies": critical_dependencies,
        }

    def _analyze_plan_coverage(self) -> Dict[str, Any]:
        """Analyze continuity plan coverage.

        Returns:
            Plan coverage analysis
        """
        coverage: Dict[str, Any] = {
            "by_scenario": {},
            "process_coverage": {},
            "gaps": [],
        }

        # Coverage by scenario type
        for plan in self.plans.values():
            scenario = plan.scenario.value
            coverage["by_scenario"][scenario] = (
                coverage["by_scenario"].get(scenario, 0) + 1
            )

        # Process coverage
        covered_processes = set()
        for plan in self.plans.values():
            covered_processes.update(plan.scope)

        coverage["process_coverage"] = {
            "covered": len(covered_processes),
            "total": len(self.processes),
            "percentage": (
                len(covered_processes) / len(self.processes) * 100
                if self.processes
                else 0
            ),
        }

        # Identify gaps
        for disruption_type in DisruptionType:
            if disruption_type.value not in coverage["by_scenario"]:
                coverage["gaps"].append(f"No plan for {disruption_type.value}")

        return coverage

    def _analyze_clinical_continuity(self) -> Dict[str, Any]:
        """Analyze clinical continuity capabilities.

        Returns:
            Clinical continuity analysis
        """
        clinical_processes = [p for p in self.processes.values() if p.clinical_process]

        return {
            "total_clinical_processes": len(clinical_processes),
            "critical_clinical_processes": len(
                [
                    p
                    for p in clinical_processes
                    if p.criticality == CriticalityLevel.CRITICAL
                ]
            ),
            "clinical_plans": len(
                [
                    plan
                    for plan in self.plans.values()
                    if any(
                        self.processes.get(pid) and self.processes[pid].clinical_process
                        for pid in plan.scope
                        if pid in self.processes
                    )
                ]
            ),
            "patient_facing_processes": len(
                [p for p in self.processes.values() if p.patient_facing]
            ),
            "clinical_recovery_strategies": [
                p.recovery_strategy.value
                for p in clinical_processes
                if p.recovery_strategy
            ],
        }

    def _check_regulatory_compliance(self) -> Dict[str, Any]:
        """Check regulatory compliance for continuity.

        Returns:
            Regulatory compliance status
        """
        compliance = {
            "cms": {
                "emergency_preparedness": len(self.plans) > 0,
                "annual_testing": self._check_annual_testing(),
                "documentation": True,  # Assumed if framework is used
            },
            "joint_commission": {
                "hva_completed": len(self.impact_analyses) > 0,
                "96_hour_plan": self._check_96_hour_sustainability(),
            },
            "hipaa": {
                "data_backup": self._check_data_backup_plans(),
                "access_controls": True,  # Assumed from other modules
            },
        }

        return compliance

    def _check_annual_testing(self) -> bool:
        """Check if annual testing requirement is met.

        Returns:
            Compliance status
        """
        current_year = datetime.now().year
        tested_this_year = any(
            t
            for t in self.test_schedule
            if t["scheduled_date"].year == current_year and t["status"] == "completed"
        )

        return tested_this_year

    def _check_96_hour_sustainability(self) -> bool:
        """Check 96-hour sustainability requirement.

        Returns:
            Compliance status
        """
        # Check if critical processes can sustain for 96 hours
        critical_processes = [
            p
            for p in self.processes.values()
            if p.criticality == CriticalityLevel.CRITICAL
        ]

        return all(p.mtpd >= 96 for p in critical_processes)

    def _check_data_backup_plans(self) -> bool:
        """Check data backup plan coverage.

        Returns:
            Compliance status
        """
        phi_processes = [p for p in self.processes.values() if p.phi_processing]

        covered = sum(
            1
            for p in phi_processes
            if any(p.process_id in plan.scope for plan in self.plans.values())
        )

        return covered == len(phi_processes)

    def _analyze_patient_impact(self) -> Dict[str, Any]:
        """Analyze potential patient impact.

        Returns:
            Patient impact analysis
        """
        patient_facing = [p for p in self.processes.values() if p.patient_facing]

        total_patient_impact = sum(
            (
                1000
                if p.criticality == CriticalityLevel.CRITICAL
                else 100 if p.criticality == CriticalityLevel.HIGH else 10
            )
            for p in patient_facing
        )

        return {
            "patient_facing_processes": len(patient_facing),
            "estimated_patients_affected": total_patient_impact,
            "critical_patient_services": [
                p.name
                for p in patient_facing
                if p.criticality == CriticalityLevel.CRITICAL
            ],
            "average_patient_rto": (
                sum(p.rto for p in patient_facing) / len(patient_facing)
                if patient_facing
                else 0
            ),
        }

    def validate_fhir_audit_event(
        self, incident_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate business continuity incident as FHIR AuditEvent.

        Args:
            incident_data: Incident data to convert and validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        # Convert to FHIR AuditEvent format
        fhir_audit_event = {
            "resourceType": "AuditEvent",
            "type": {
                "system": "http://terminology.hl7.org/CodeSystem/iso27001-audit",
                "code": "business-continuity",
                "display": "Business Continuity Event",
            },
            "subtype": [
                {
                    "system": "http://havenhealthpassport.org/CodeSystem/bc-event",
                    "code": incident_data.get("incident_type", "unknown"),
                    "display": incident_data.get(
                        "description", "Business continuity event"
                    ),
                }
            ],
            "action": incident_data.get("action_taken", "U"),
            "period": {
                "start": incident_data.get(
                    "detection_time", datetime.now()
                ).isoformat(),
                "end": (
                    incident_data.get("resolution_time", "").isoformat()
                    if incident_data.get("resolution_time")
                    else None
                ),
            },
            "recorded": datetime.now().isoformat(),
            "outcome": "0" if incident_data.get("status") == "resolved" else "8",
            "outcomeDesc": incident_data.get("resolution_notes"),
            "agent": [
                {
                    "who": {"display": incident_data.get("reported_by", "System")},
                    "requestor": True,
                }
            ],
            "source": {
                "observer": {"display": "Business Continuity Management System"}
            },
            "entity": [
                {
                    "what": {
                        "display": f"Process: {incident_data.get('affected_processes', ['Unknown'])[0]}"
                    },
                    "type": {
                        "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                        "code": "2",
                        "display": "System Object",
                    },
                    "detail": [
                        {
                            "type": "impact",
                            "valueString": incident_data.get("impact", "Unknown"),
                        }
                    ],
                }
            ],
        }

        # Validate using FHIR validator
        return self.fhir_validator.validate_resource("AuditEvent", fhir_audit_event)


# Export public API
__all__ = [
    "BusinessContinuityFramework",
    "BusinessProcess",
    "BusinessContinuityPlan",
    "CriticalityLevel",
    "DisruptionType",
    "RecoveryStrategy",
    "TestType",
]
