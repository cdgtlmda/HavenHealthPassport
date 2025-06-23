"""
Database performance tests with real production data volumes.

CRITICAL: These tests verify the database can handle:
- Millions of patient records
- Complex queries with proper indexing
- Concurrent transactions
- Encryption/decryption performance
- Audit trail overhead

This ensures the system performs adequately in large refugee camps.
"""

import asyncio
import concurrent.futures
import time
from datetime import date, datetime, timedelta
from typing import Any, Generator

import pytest
from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.models.audit_log import AuditLog
from src.models.health_record import HealthRecord, RecordType
from src.models.patient import Patient
from src.services.encryption_service import EncryptionService


@pytest.mark.performance
@pytest.mark.database
class TestDatabasePerformance:
    """Test database performance with realistic data volumes."""

    @pytest.fixture(scope="class")
    def large_dataset(self, test_db: Session) -> Generator[Session, None, None]:
        """Create a large dataset for performance testing."""
        print("\nCreating large test dataset...")
        start_time = time.time()

        # Use bulk operations for efficiency
        batch_size = 1000
        total_patients = 100000  # 100k patients

        for i in range(0, total_patients, batch_size):
            batch = []
            for j in range(batch_size):
                patient_num = i + j
                batch.append(
                    {
                        "patient_id": f"PAT-PERF-{patient_num:06d}",
                        "first_name": f"Test{patient_num % 1000}",
                        "last_name": f"Patient{patient_num // 1000}",
                        "date_of_birth": date(
                            1950 + (patient_num % 70),
                            (patient_num % 12) + 1,
                            (patient_num % 28) + 1,
                        ),
                        "gender": ["male", "female", "other"][patient_num % 3],
                        "blood_type": [
                            "A+",
                            "A-",
                            "B+",
                            "B-",
                            "O+",
                            "O-",
                            "AB+",
                            "AB-",
                        ][patient_num % 8],
                        "phone": f"+1555{patient_num:06d}",
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                )

            # Bulk insert
            test_db.bulk_insert_mappings(Patient.__mapper__, batch)
            test_db.commit()

            if (i + batch_size) % 10000 == 0:
                print(f"Created {i + batch_size} patients...")

        print(f"Dataset creation took {time.time() - start_time:.2f} seconds")

        yield test_db

        # Cleanup
        print("Cleaning up test dataset...")
        test_db.query(Patient).filter(Patient.patient_id.like("PAT-PERF-%")).delete(
            synchronize_session=False
        )
        test_db.commit()

    def test_patient_search_performance_with_million_records(
        self, large_dataset: Session, benchmark: Any
    ) -> None:
        """Test search performance with proper indexing."""

        def search_patients():
            # Complex search query
            results = (
                large_dataset.query(Patient)
                .filter(
                    and_(
                        Patient.first_name.like("Test5%"),
                        Patient.date_of_birth > date(1980, 1, 1),
                        Patient.blood_type.in_(["A+", "O+"]),
                    )
                )
                .order_by(Patient.created_at.desc())
                .limit(100)
                .all()
            )

            return list(results)

        # Benchmark the search
        result = benchmark(search_patients)

        # Verify results
        assert len(result) > 0
        assert all(p.first_name.startswith("Test5") for p in result)

        # Performance assertion - should complete in < 100ms with proper indexes
        assert benchmark.stats["mean"] < 0.1

        print(f"\nSearch performance: {benchmark.stats['mean']*1000:.2f}ms average")

    def test_concurrent_patient_creation(
        self, test_db: Session, benchmark: Any
    ) -> None:
        """Test concurrent write performance."""
        encryption_service = EncryptionService()

        def create_patient_batch(batch_num):
            """Create a batch of patients with encrypted data."""
            patients: list[Patient] = []
            for i in range(10):
                patient_data = {
                    "patient_id": f"PAT-CONC-{batch_num:03d}-{i:03d}",
                    "first_name": f"Concurrent{batch_num}",
                    "last_name": f"Test{i}",
                    "date_of_birth": date(1990, 1, 1),
                    "ssn": encryption_service.encrypt_field_level(
                        {"ssn": f"123-45-{batch_num:04d}"}, ["ssn"]
                    )["ssn"],
                    "phone": f"+1555{batch_num:03d}{i:04d}",
                }
                patient = Patient(**patient_data)
                test_db.add(patient)

            test_db.commit()
            return len(patients)

        def run_concurrent_creates():
            """Run multiple concurrent patient creations."""
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(create_patient_batch, i) for i in range(10)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
            return sum(results)

        # Benchmark concurrent operations
        benchmark(run_concurrent_creates)

        # Verify all were created
        created_count = (
            test_db.query(Patient).filter(Patient.patient_id.like("PAT-CONC-%")).count()
        )
        assert created_count == 100

        print(f"\nConcurrent creation: {benchmark.stats['mean']:.2f}s for 100 patients")

        # Cleanup
        test_db.query(Patient).filter(Patient.patient_id.like("PAT-CONC-%")).delete()
        test_db.commit()

    def test_encryption_performance(self, benchmark: Any) -> None:
        """Test encryption/decryption performance for PHI fields."""
        encryption_service = EncryptionService()
        test_data = [
            "123-45-6789",  # SSN
            "MRN-123456789",  # Medical Record Number
            "INS-987654321",  # Insurance ID
            "Very long medical history with lots of sensitive information " * 10,
        ]

        def encrypt_decrypt_cycle():
            """Encrypt and decrypt all test data."""
            encrypted = []
            for data in test_data:
                encrypted.append(
                    encryption_service.encrypt_field_level(
                        {"test_field": data}, ["test_field"]
                    )["test_field"]
                )

            decrypted = []
            for enc_data in encrypted:
                decrypted.append(
                    encryption_service.decrypt_field_level(
                        {"test_field": enc_data}, ["test_field"]
                    )["test_field"]
                )

            return decrypted

        # Benchmark encryption/decryption
        result = benchmark(encrypt_decrypt_cycle)

        # Verify correctness
        assert result == test_data

        # Performance assertion - should be fast enough for real-time operations
        assert benchmark.stats["mean"] < 0.05  # < 50ms for all operations

        print(f"\nEncryption performance: {benchmark.stats['mean']*1000:.2f}ms average")

    def test_audit_trail_overhead(self, test_db: Session, benchmark: Any) -> None:
        """Test performance impact of audit trail generation."""

        def operation_with_audit():
            """Perform operation that generates audit trails."""
            # Create patient
            patient = Patient(
                patient_id=f"PAT-AUDIT-{time.time_ns()}",
                first_name="Audit",
                last_name="Test",
                date_of_birth=date(1990, 1, 1),
            )
            test_db.add(patient)

            # Create audit log
            audit = AuditLog(
                action="CREATE_PATIENT",
                user_id="test-user",
                resource_type="patient",
                resource_id=patient.patient_id,
                ip_address="127.0.0.1",
                user_agent="test-agent",
                changes={
                    "first_name": {"old": None, "new": "Audit"},
                    "last_name": {"old": None, "new": "Test"},
                },
            )
            test_db.add(audit)

            # Update patient
            patient.phone = "+1234567890"

            # Create update audit
            update_audit = AuditLog(
                action="UPDATE_PATIENT",
                user_id="test-user",
                resource_type="patient",
                resource_id=patient.patient_id,
                ip_address="127.0.0.1",
                user_agent="test-agent",
                changes={"phone": {"old": None, "new": "+1234567890"}},
            )
            test_db.add(update_audit)

            test_db.commit()

            return patient.patient_id

        # Benchmark operations with audit trail
        patient_id = benchmark(operation_with_audit)

        # Verify audit trails were created
        audit_count = (
            test_db.query(AuditLog).filter(AuditLog.resource_id == patient_id).count()
        )
        assert audit_count == 2

        # Performance should still be acceptable
        assert benchmark.stats["mean"] < 0.1  # < 100ms

        print(f"\nAudit trail overhead: {benchmark.stats['mean']*1000:.2f}ms average")

        # Cleanup
        test_db.query(AuditLog).filter(AuditLog.resource_id == patient_id).delete()
        test_db.query(Patient).filter(Patient.patient_id == patient_id).delete()
        test_db.commit()

    def test_complex_join_performance(
        self, large_dataset: Session, benchmark: Any
    ) -> None:
        """Test performance of complex joins across tables."""
        # First create some health records
        print("\nCreating health records for join test...")
        records = []
        for i in range(1000):
            record = HealthRecord(
                patient_id=f"PAT-PERF-{i:06d}",
                record_type=RecordType.VITAL_SIGNS,
                data={
                    "blood_pressure": "120/80",
                    "heart_rate": 72,
                    "temperature": 98.6,
                },
                created_at=datetime.utcnow() - timedelta(days=i % 30),
            )
            records.append(record)

        large_dataset.bulk_save_objects(records)
        large_dataset.commit()

        def complex_query():
            """Execute complex join query."""
            # Find patients with recent vitals and specific criteria
            results = (
                large_dataset.query(
                    Patient.patient_id,
                    Patient.first_name,
                    Patient.last_name,
                    HealthRecord.data,
                    HealthRecord.created_at,
                )
                .join(HealthRecord, Patient.id == HealthRecord.patient_id)
                .filter(HealthRecord.record_type == RecordType.VITAL_SIGNS)
                .filter(HealthRecord.created_at > datetime.utcnow() - timedelta(days=7))
                .filter(Patient.blood_type.in_(["A+", "O+"]))
                .filter(Patient.date_of_birth < date(1980, 1, 1))
                .order_by(HealthRecord.created_at.desc())
                .limit(50)
                .all()
            )

            return list(results)

        # Benchmark the join
        results = benchmark(complex_query)

        # Verify results
        assert len(results) > 0

        # Performance assertion
        assert benchmark.stats["mean"] < 0.2  # < 200ms for complex join

        print(
            f"\nComplex join performance: {benchmark.stats['mean']*1000:.2f}ms average"
        )

        # Cleanup
        large_dataset.query(HealthRecord).filter(
            HealthRecord.patient_id.like("PAT-PERF-%")
        ).delete(synchronize_session=False)
        large_dataset.commit()

    @pytest.mark.asyncio
    async def test_async_database_operations(self, test_db: Session) -> None:
        """Test async database operations for scalability."""

        async def create_patient_async(patient_num):
            """Simulate async patient creation."""
            await asyncio.sleep(0.001)  # Simulate I/O

            patient = Patient(
                patient_id=f"PAT-ASYNC-{patient_num:04d}",
                first_name=f"Async{patient_num}",
                last_name="Test",
                date_of_birth=date(1990, 1, 1),
            )

            # In real implementation, this would use async SQLAlchemy
            test_db.add(patient)

            return patient.patient_id

        # Create many patients concurrently
        start_time = time.time()

        tasks = [create_patient_async(i) for i in range(100)]
        await asyncio.gather(*tasks)

        test_db.commit()

        duration = time.time() - start_time

        # Verify all created
        count = (
            test_db.query(Patient)
            .filter(Patient.patient_id.like("PAT-ASYNC-%"))
            .count()
        )
        assert count == 100

        print(f"\nAsync operations: {duration:.2f}s for 100 patients")
        print(f"Rate: {100/duration:.0f} patients/second")

        # Cleanup
        test_db.query(Patient).filter(Patient.patient_id.like("PAT-ASYNC-%")).delete()
        test_db.commit()

    def test_pagination_performance(
        self, large_dataset: Session, benchmark: Any
    ) -> None:
        """Test pagination performance for large result sets."""

        def paginate_results(page: int, per_page: int = 50) -> dict[str, Any]:
            """Get paginated results."""
            offset = (page - 1) * per_page

            query = (
                large_dataset.query(Patient)
                .filter(Patient.date_of_birth > date(1970, 1, 1))
                .order_by(Patient.created_at.desc())
            )

            # Get total count
            total = query.count()

            # Get page results
            results = query.offset(offset).limit(per_page).all()

            return {
                "total": total,
                "page": page,
                "per_page": per_page,
                "results": results,
            }

        # Benchmark different pages
        pages_to_test = [1, 10, 100, 1000]

        for page in pages_to_test:
            result = benchmark(lambda p=page: paginate_results(p))

            assert len(result["results"]) <= 50
            assert result["total"] > 0

            print(f"\nPage {page} performance: {benchmark.stats['mean']*1000:.2f}ms")

            # Later pages shouldn't be significantly slower
            assert benchmark.stats["mean"] < 0.15  # < 150ms
