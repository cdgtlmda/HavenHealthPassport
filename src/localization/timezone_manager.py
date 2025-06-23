"""Time Zone Management for Global Healthcare.

This module provides time zone management for healthcare applications
serving users across different time zones.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# from src.healthcare.hipaa_access_control import (
#     AccessLevel,
#     require_phi_access,
# )  # Available if needed for HIPAA compliance
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

# Create timezone compatibility layer
UTC: Any  # Type depends on available timezone library

try:
    from zoneinfo import ZoneInfo

    def get_timezone(name: str) -> Any:
        """Get timezone object."""
        if name == "UTC":
            return dt_timezone.utc
        return ZoneInfo(name)

    UTC = dt_timezone.utc

except ImportError:
    import pytz as _pytz

    def get_timezone(name: str) -> Any:
        """Get timezone object."""
        return _pytz.timezone(name)

    UTC = _pytz.UTC

logger = get_logger(__name__)


class TimeFormat(str, Enum):
    """Time display formats."""

    HOUR_12 = "12h"  # 12-hour with AM/PM
    HOUR_24 = "24h"  # 24-hour military time
    MEDICAL = "medical"  # 24-hour with seconds


@dataclass
class TimeZonePreference:
    """User's time zone preferences."""

    primary_timezone: str  # IANA timezone ID
    display_format: TimeFormat
    show_timezone_name: bool = True
    show_utc_offset: bool = False
    auto_detect: bool = True


@dataclass
class AppointmentTime:
    """Appointment time with timezone info."""

    local_time: datetime
    utc_time: datetime
    timezone: str
    timezone_abbr: str
    utc_offset: str
    is_dst: bool


class TimeZoneManager:
    """Manages time zones for healthcare scheduling."""

    # Common time zones for refugee populations
    REFUGEE_COMMON_TIMEZONES = {
        "camps": {
            "Dadaab_Kenya": "Africa/Nairobi",
            "Kakuma_Kenya": "Africa/Nairobi",
            "Zaatari_Jordan": "Asia/Amman",
            "Cox_Bazar_Bangladesh": "Asia/Dhaka",
            "Lesbos_Greece": "Europe/Athens",
        },
        "regions": {
            "East_Africa": ["Africa/Nairobi", "Africa/Addis_Ababa", "Africa/Kampala"],
            "Middle_East": [
                "Asia/Damascus",
                "Asia/Baghdad",
                "Asia/Kabul",
                "Asia/Tehran",
            ],
            "South_Asia": ["Asia/Dhaka", "Asia/Karachi", "Asia/Kolkata"],
            "Southeast_Asia": ["Asia/Yangon", "Asia/Bangkok", "Asia/Jakarta"],
        },
    }

    # Medical facility time zones (for telemedicine)
    MEDICAL_FACILITIES = {
        "MSF_HQ": "Europe/Paris",
        "WHO_Geneva": "Europe/Zurich",
        "UNHCR_Geneva": "Europe/Zurich",
        "Johns_Hopkins": "America/New_York",
        "Mayo_Clinic": "America/Chicago",
    }

    def __init__(self) -> None:
        """Initialize timezone manager."""
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self.user_timezones: Dict[str, TimeZonePreference] = {}

    def convert_appointment_time(
        self,
        appointment_dt: datetime,
        from_timezone: str,
        to_timezone: str,
        include_dst_warning: bool = True,
    ) -> AppointmentTime:
        """Convert appointment time between timezones."""
        # Get timezone objects
        from_tz = get_timezone(from_timezone)
        to_tz = get_timezone(to_timezone)

        # Localize to source timezone
        if appointment_dt.tzinfo is None:
            localized_dt = from_tz.localize(appointment_dt)
        else:
            localized_dt = appointment_dt.astimezone(from_tz)

        # Convert to UTC
        utc_dt = localized_dt.astimezone(UTC)

        # Convert to target timezone
        target_dt = utc_dt.astimezone(to_tz)

        # Get timezone info
        tz_abbr = target_dt.strftime("%Z")
        utc_offset = target_dt.strftime("%z")
        is_dst = bool(target_dt.dst())

        # Format UTC offset
        if utc_offset:
            hours = int(utc_offset[:3])
            minutes = int(utc_offset[3:5]) if len(utc_offset) > 3 else 0
            utc_offset_formatted = f"UTC{hours:+03d}:{minutes:02d}"
        else:
            utc_offset_formatted = "UTC+00:00"

        return AppointmentTime(
            local_time=target_dt,
            utc_time=utc_dt,
            timezone=to_timezone,
            timezone_abbr=tz_abbr,
            utc_offset=utc_offset_formatted,
            is_dst=is_dst,
        )

    def get_appointment_times_multiple_zones(
        self, appointment_utc: datetime, timezones: List[str], format_time: bool = True
    ) -> Dict[str, Any]:
        """Get appointment time in multiple timezones."""
        results = {}

        for timezone_id in timezones:
            try:
                tz = get_timezone(timezone_id)
                local_time = appointment_utc.astimezone(tz)

                results[timezone_id] = {
                    "datetime": local_time,
                    "formatted": (
                        self._format_datetime(local_time) if format_time else None
                    ),
                    "timezone_abbr": local_time.strftime("%Z"),
                    "utc_offset": local_time.strftime("%z"),
                    "is_dst": bool(local_time.dst()),
                }
            except Exception as e:
                logger.error(f"Error converting to timezone {timezone_id}: {e}")
                results[timezone_id] = {"error": str(e)}

        return results

    def _format_datetime(
        self, dt: datetime, format_type: TimeFormat = TimeFormat.MEDICAL
    ) -> str:
        """Format datetime according to preference."""
        if format_type == TimeFormat.HOUR_12:
            return dt.strftime("%Y-%m-%d %I:%M %p %Z")
        elif format_type == TimeFormat.HOUR_24:
            return dt.strftime("%Y-%m-%d %H:%M %Z")
        else:  # Medical format
            return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

    def calculate_medication_schedule(
        self,
        start_time: datetime,
        frequency_hours: int,
        doses: int,
        patient_timezone: str,
        show_all_times: bool = True,
    ) -> List[Dict[str, Any]]:
        """Calculate medication schedule across timezones."""
        schedule = []

        patient_tz = get_timezone(patient_timezone)

        # Ensure start_time is timezone-aware
        if start_time.tzinfo is None:
            start_time = patient_tz.localize(start_time)

        for dose_num in range(doses):
            dose_time = start_time + timedelta(hours=frequency_hours * dose_num)

            # Convert to patient's local time
            local_dose_time = dose_time.astimezone(patient_tz)

            dose_info = {
                "dose_number": dose_num + 1,
                "local_time": local_dose_time,
                "formatted_time": self._format_medication_time(local_dose_time),
                "utc_time": dose_time.astimezone(UTC),
            }

            # Add relative time
            if dose_num == 0:
                dose_info["relative"] = "First dose"
            else:
                hours_from_start = frequency_hours * dose_num
                dose_info["relative"] = f"{hours_from_start} hours after first dose"

            schedule.append(dose_info)

        return schedule

    def _format_medication_time(self, dt: datetime) -> str:
        """Format time for medication schedule."""
        # Use simple format for medication times
        today = datetime.now(dt.tzinfo).date()

        if dt.date() == today:
            day_part = "Today"
        elif dt.date() == today + timedelta(days=1):
            day_part = "Tomorrow"
        else:
            day_part = dt.strftime("%A, %B %d")

        time_part = dt.strftime("%I:%M %p")

        return f"{day_part} at {time_part}"

    def get_business_hours_overlap(
        self,
        facility_timezone: str,
        patient_timezone: str,
        facility_hours: Tuple[int, int] = (9, 17),  # 9 AM to 5 PM
    ) -> Dict[str, Any]:
        """Find overlapping business hours for scheduling."""
        facility_tz = get_timezone(facility_timezone)
        patient_tz = get_timezone(patient_timezone)

        # Create sample date (today)
        today = datetime.now().date()

        # Facility business hours
        facility_start = facility_tz.localize(
            datetime.combine(today, datetime.min.time().replace(hour=facility_hours[0]))
        )
        facility_end = facility_tz.localize(
            datetime.combine(today, datetime.min.time().replace(hour=facility_hours[1]))
        )

        # Convert to patient timezone
        patient_start = facility_start.astimezone(patient_tz)
        patient_end = facility_end.astimezone(patient_tz)

        # Check if hours cross midnight
        crosses_midnight = patient_end.date() > patient_start.date()

        return {
            "facility_timezone": facility_timezone,
            "patient_timezone": patient_timezone,
            "facility_hours": f"{facility_hours[0]:02d}:00 - {facility_hours[1]:02d}:00",
            "patient_hours": {
                "start": patient_start.strftime("%H:%M"),
                "end": patient_end.strftime("%H:%M"),
                "formatted": f"{patient_start.strftime('%I:%M %p')} - {patient_end.strftime('%I:%M %p')}",
            },
            "crosses_midnight": crosses_midnight,
            "optimal_times": self._suggest_optimal_times(patient_start, patient_end),
        }

    def _suggest_optimal_times(self, start: datetime, end: datetime) -> List[str]:
        """Suggest optimal appointment times."""
        suggestions = []

        # Suggest times at regular intervals
        current = start
        while current < end:
            if current.hour >= 8 and current.hour <= 20:  # Reasonable hours
                suggestions.append(current.strftime("%I:%M %p"))
            current += timedelta(hours=1)

        return suggestions[:5]  # Return top 5 suggestions

    def handle_dst_transition(
        self, appointment_dt: datetime, timezone_id: str
    ) -> Dict[str, Any]:
        """Handle daylight saving time transitions."""
        tz = get_timezone(timezone_id)

        # Check if date is near DST transition
        transition_info: Dict[str, Any] = {
            "has_dst": self._timezone_has_dst(timezone_id),
            "is_dst": False,
            "transition_warning": None,
        }

        if transition_info["has_dst"]:
            # Localize and check DST
            if appointment_dt.tzinfo is None:
                local_dt = tz.localize(appointment_dt)
            else:
                local_dt = appointment_dt.astimezone(tz)

            transition_info["is_dst"] = bool(local_dt.dst())

            # Check if within a week of transition
            warning = self._check_dst_transition_proximity(local_dt, tz)
            if warning:
                transition_info["transition_warning"] = warning

        return transition_info

    def _timezone_has_dst(self, timezone_id: str) -> bool:
        """Check if timezone observes DST."""
        # Timezones that don't observe DST
        no_dst_zones = {
            "Asia/Kolkata",
            "Asia/Dhaka",
            "Asia/Karachi",
            "Asia/Dubai",
            "Asia/Singapore",
            "Africa/Lagos",
            "Africa/Nairobi",
            "Asia/Tokyo",
            "Asia/Shanghai",
        }

        return timezone_id not in no_dst_zones

    def _check_dst_transition_proximity(self, dt: datetime, tz: Any) -> Optional[str]:
        """Check if date is near DST transition."""
        # This is simplified - in production would check actual transition dates
        # Most DST transitions happen in March and November
        if dt.month in [3, 11]:
            return "This appointment is scheduled near a daylight saving time change. Please confirm the time after the transition."

        return None

    def get_timezone_info(self, timezone_id: str) -> Dict[str, Any]:
        """Get detailed timezone information."""
        try:
            tz = get_timezone(timezone_id)
            now = datetime.now(tz)

            return {
                "timezone_id": timezone_id,
                "current_time": now,
                "utc_offset": now.strftime("%z"),
                "timezone_abbr": now.strftime("%Z"),
                "is_dst": bool(now.dst()),
                "has_dst": self._timezone_has_dst(timezone_id),
                "country": self._get_timezone_country(timezone_id),
                "common_name": self._get_timezone_common_name(timezone_id),
            }
        except Exception as e:
            logger.error(f"Error getting timezone info for {timezone_id}: {e}")
            return {"error": str(e)}

    def _get_timezone_country(self, timezone_id: str) -> str:
        """Get country for timezone."""
        # Simple mapping - in production would use comprehensive database
        parts = timezone_id.split("/")
        if len(parts) >= 2:
            return parts[1].replace("_", " ")
        return timezone_id

    def _get_timezone_common_name(self, timezone_id: str) -> str:
        """Get common name for timezone."""
        common_names = {
            "America/New_York": "Eastern Time",
            "America/Chicago": "Central Time",
            "America/Denver": "Mountain Time",
            "America/Los_Angeles": "Pacific Time",
            "Europe/London": "British Time",
            "Europe/Paris": "Central European Time",
            "Asia/Kolkata": "India Standard Time",
            "Asia/Shanghai": "China Standard Time",
        }

        return common_names.get(timezone_id, timezone_id)


# Global timezone manager instance
timezone_manager = TimeZoneManager()
