"""Test thread-safe singleton implementations in security modules."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.config.webauthn_settings import get_webauthn_settings
from src.security.encryption import get_encryption_service
from src.security.intrusion_detection_system import get_intrusion_detection_system
from src.security.key_management.kms_configuration import get_kms_configuration
from src.security.phi_protection import get_phi_protection


class TestThreadSafeSingletons:
    """Test that our security singletons are thread-safe."""

    def test_encryption_service_singleton(self):
        """Test EncryptionService singleton is thread-safe."""
        instances = []

        def get_instance():
            instances.append(get_encryption_service())

        # Create multiple threads trying to get the instance
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=get_instance)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All instances should be the same
        assert all(instance is instances[0] for instance in instances)

    def test_phi_protection_singleton(self):
        """Test PHI protection singleton is thread-safe."""
        instances = []

        def get_instance():
            instances.append(get_phi_protection())

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(get_instance) for _ in range(20)]
            for future in as_completed(futures):
                future.result()

        # All instances should be the same
        assert all(instance is instances[0] for instance in instances)

    def test_kms_configuration_singleton(self):
        """Test KMS configuration singleton is thread-safe."""
        instances = []

        def get_instance():
            instances.append(get_kms_configuration())

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(get_instance) for _ in range(15)]
            for future in as_completed(futures):
                future.result()

        # All instances should be the same
        assert all(instance is instances[0] for instance in instances)

    def test_concurrent_access_no_race_conditions(self):
        """Test that concurrent access doesn't cause race conditions."""
        results = []
        errors = []

        def access_services():
            try:
                # Access multiple services in each thread
                enc_service = get_encryption_service()
                phi_protection = get_phi_protection()
                kms_config = get_kms_configuration()

                # Simulate some work
                time.sleep(0.001)

                # Store results
                results.append(
                    {
                        "encryption": enc_service,
                        "phi": phi_protection,
                        "kms": kms_config,
                    }
                )
            except Exception as e:
                errors.append(e)

        # Run many threads concurrently
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(access_services) for _ in range(100)]
            for future in as_completed(futures):
                future.result()

        # No errors should occur
        assert len(errors) == 0

        # All instances of each service should be the same
        if results:
            first_result = results[0]
            for result in results:
                assert result["encryption"] is first_result["encryption"]
                assert result["phi"] is first_result["phi"]
                assert result["kms"] is first_result["kms"]

    def test_all_singletons_unique(self):
        """Test that different singleton classes return different instances."""
        enc_service = get_encryption_service()
        phi_protection = get_phi_protection()
        kms_config = get_kms_configuration()
        ids_system = get_intrusion_detection_system()
        webauthn_settings = get_webauthn_settings()

        # All should be different types
        instances = [
            enc_service,
            phi_protection,
            kms_config,
            ids_system,
            webauthn_settings,
        ]
        types_seen = set()

        for instance in instances:
            instance_type = type(instance)
            assert (
                instance_type not in types_seen
            ), f"Duplicate type found: {instance_type}"
            types_seen.add(instance_type)
