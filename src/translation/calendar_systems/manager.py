"""Calendar system manager implementation."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union, cast

from src.utils.logging import get_logger

from .coptic import CopticCalendarConverter
from .ethiopian import EthiopianCalendarConverter
from .hebrew import HebrewCalendarConverter
from .nepali import NepaliCalendarConverter
from .types import CalendarConfig, CalendarDate, CalendarSystem
from .utils import CalendarUtils

try:
    from hijri_converter import Gregorian, Hijri
except ImportError:
    Hijri = None
    Gregorian = None

try:
    import jdatetime  # Persian calendar
except ImportError:
    jdatetime = None

logger = get_logger(__name__)


class CalendarManager:
    """Manages multiple calendar systems and conversions."""

    # Calendar configurations
    CALENDAR_CONFIGS = {
        CalendarSystem.GREGORIAN: CalendarConfig(
            system=CalendarSystem.GREGORIAN,
            month_names={
                "en": [
                    "January",
                    "February",
                    "March",
                    "April",
                    "May",
                    "June",
                    "July",
                    "August",
                    "September",
                    "October",
                    "November",
                    "December",
                ],
                "ar": [
                    "يناير",
                    "فبراير",
                    "مارس",
                    "أبريل",
                    "مايو",
                    "يونيو",
                    "يوليو",
                    "أغسطس",
                    "سبتمبر",
                    "أكتوبر",
                    "نوفمبر",
                    "ديسمبر",
                ],
                "fa": [
                    "ژانویه",
                    "فوریه",
                    "مارس",
                    "آوریل",
                    "مه",
                    "ژوئن",
                    "ژوئیه",
                    "اوت",
                    "سپتامبر",
                    "اکتبر",
                    "نوامبر",
                    "دسامبر",
                ],
            },
            day_names={
                "en": [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ],
                "ar": [
                    "الإثنين",
                    "الثلاثاء",
                    "الأربعاء",
                    "الخميس",
                    "الجمعة",
                    "السبت",
                    "الأحد",
                ],
                "fa": [
                    "دوشنبه",
                    "سه‌شنبه",
                    "چهارشنبه",
                    "پنج‌شنبه",
                    "جمعه",
                    "شنبه",
                    "یکشنبه",
                ],
            },
            era_names={
                "en": {"before": "BCE", "after": "CE"},
                "ar": {"before": "ق.م", "after": "م"},
                "fa": {"before": "پیش از میلاد", "after": "میلادی"},
            },
            first_day_of_week=0,  # Monday
            weekend_days=[5, 6],  # Saturday, Sunday
            date_format="DD/MM/YYYY",
        ),
        CalendarSystem.HIJRI: CalendarConfig(
            system=CalendarSystem.HIJRI,
            month_names={
                "en": [
                    "Muharram",
                    "Safar",
                    "Rabi' al-awwal",
                    "Rabi' al-thani",
                    "Jumada al-awwal",
                    "Jumada al-thani",
                    "Rajab",
                    "Sha'ban",
                    "Ramadan",
                    "Shawwal",
                    "Dhu al-Qi'dah",
                    "Dhu al-Hijjah",
                ],
                "ar": [
                    "محرم",
                    "صفر",
                    "ربيع الأول",
                    "ربيع الثاني",
                    "جمادى الأولى",
                    "جمادى الثانية",
                    "رجب",
                    "شعبان",
                    "رمضان",
                    "شوال",
                    "ذو القعدة",
                    "ذو الحجة",
                ],
                "ur": [
                    "محرم",
                    "صفر",
                    "ربیع الاول",
                    "ربیع الثانی",
                    "جمادی الاول",
                    "جمادی الثانی",
                    "رجب",
                    "شعبان",
                    "رمضان",
                    "شوال",
                    "ذیقعد",
                    "ذی الحجہ",
                ],
            },
            day_names={
                "en": [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ],
                "ar": [
                    "الإثنين",
                    "الثلاثاء",
                    "الأربعاء",
                    "الخميس",
                    "الجمعة",
                    "السبت",
                    "الأحد",
                ],
            },
            era_names={"en": {"after": "AH"}, "ar": {"after": "هـ"}},
            first_day_of_week=6,  # Sunday
            weekend_days=[4, 5],  # Friday, Saturday
            date_format="DD/MM/YYYY",
        ),
        CalendarSystem.PERSIAN: CalendarConfig(
            system=CalendarSystem.PERSIAN,
            month_names={
                "en": [
                    "Farvardin",
                    "Ordibehesht",
                    "Khordad",
                    "Tir",
                    "Mordad",
                    "Shahrivar",
                    "Mehr",
                    "Aban",
                    "Azar",
                    "Dey",
                    "Bahman",
                    "Esfand",
                ],
                "fa": [
                    "فروردین",
                    "اردیبهشت",
                    "خرداد",
                    "تیر",
                    "مرداد",
                    "شهریور",
                    "مهر",
                    "آبان",
                    "آذر",
                    "دی",
                    "بهمن",
                    "اسفند",
                ],
                "ps": [
                    "وری",
                    "غويی",
                    "غبرګولی",
                    "چنګاښ",
                    "زمری",
                    "وږی",
                    "تله",
                    "لړم",
                    "ليندۍ",
                    "مرغومی",
                    "سلواغه",
                    "کب",
                ],
            },
            day_names={
                "en": [
                    "Saturday",
                    "Sunday",
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                ],
                "fa": [
                    "شنبه",
                    "یکشنبه",
                    "دوشنبه",
                    "سه‌شنبه",
                    "چهارشنبه",
                    "پنج‌شنبه",
                    "جمعه",
                ],
            },
            era_names={"en": {"after": "SH"}, "fa": {"after": "ش.ه"}},
            first_day_of_week=5,  # Saturday
            weekend_days=[4],  # Friday
            date_format="YYYY/MM/DD",
        ),
        CalendarSystem.ETHIOPIAN: CalendarConfig(
            system=CalendarSystem.ETHIOPIAN,
            month_names={
                "en": [
                    "Meskerem",
                    "Tikimt",
                    "Hidar",
                    "Tahsas",
                    "Tir",
                    "Yakatit",
                    "Maggabit",
                    "Miyazya",
                    "Ginbot",
                    "Sene",
                    "Hamle",
                    "Nehase",
                    "Pagume",
                ],
                "am": [
                    "መስከረም",
                    "ጥቅምት",
                    "ኅዳር",
                    "ታኅሣሥ",
                    "ጥር",
                    "የካቲት",
                    "መጋቢት",
                    "ሚያዝያ",
                    "ግንቦት",
                    "ሰኔ",
                    "ሐምሌ",
                    "ነሐሴ",
                    "ጳጉሜ",
                ],
                "ti": [
                    "መስከረም",
                    "ጥቅምቲ",
                    "ሕዳር",
                    "ታሕሳስ",
                    "ጥሪ",
                    "ለካቲት",
                    "መጋቢት",
                    "ሚያዝያ",
                    "ግንቦት",
                    "ሰነ",
                    "ሓምለ",
                    "ነሓሰ",
                    "ጳጉሜ",
                ],
            },
            day_names={
                "en": [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ],
                "am": [
                    "ሰኞ",
                    "ማክሰኞ",
                    "ረቡዕ",
                    "ሐሙስ",
                    "ዓርብ",
                    "ቅዳሜ",
                    "እሑድ",
                ],
            },
            era_names={
                "en": {"before": "BC", "after": "EC"},
                "am": {"before": "ዓ.ዓ", "after": "ዓ.ም"},
            },
            first_day_of_week=6,  # Sunday
            weekend_days=[5, 6],  # Saturday, Sunday
            date_format="DD/MM/YYYY",
        ),
        CalendarSystem.COPTIC: CalendarConfig(
            system=CalendarSystem.COPTIC,
            month_names={
                "en": [
                    "Thout",
                    "Paopi",
                    "Hathor",
                    "Koiak",
                    "Tobi",
                    "Meshir",
                    "Paremhat",
                    "Paremoude",
                    "Pashons",
                    "Paoni",
                    "Epip",
                    "Mesori",
                    "Pi Kogi Enavot",
                ],
                "cop": [
                    "Ⲑⲱⲟⲩⲧ",
                    "Ⲡⲁⲱⲡⲉ",
                    "Ϩⲁⲑⲱⲣ",
                    "Ⲕⲟⲓⲁⲕ",
                    "Ⲧⲱⲃⲉ",
                    "Ⲙⲉϣⲓⲣ",
                    "Ⲡⲁⲣⲉⲙϩⲁⲧ",
                    "Ⲡⲁⲣⲙⲟⲩⲧⲉ",
                    "Ⲡⲁϣⲟⲛⲥ",
                    "Ⲡⲁⲱⲛⲉ",
                    "Ⲉⲡⲓⲡ",
                    "Ⲙⲉⲥⲱⲣⲉ",
                    "Ⲡⲓⲕⲟⲩϫⲓ ⲛ̀ⲁⲃⲟⲧ",
                ],
            },
            day_names={
                "en": [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ],
            },
            era_names={
                "en": {"after": "AM"},  # Anno Martyrum
            },
            first_day_of_week=6,  # Sunday
            weekend_days=[5, 6],  # Saturday, Sunday
            date_format="DD/MM/YYYY",
        ),
        CalendarSystem.HEBREW: CalendarConfig(
            system=CalendarSystem.HEBREW,
            month_names={
                "en": [
                    "Tishrei",
                    "Cheshvan",
                    "Kislev",
                    "Tevet",
                    "Shevat",
                    "Adar",
                    "Nisan",
                    "Iyar",
                    "Sivan",
                    "Tammuz",
                    "Av",
                    "Elul",
                    "Adar II",
                ],
                "he": [
                    "תשרי",
                    "חשוון",
                    "כסלו",
                    "טבת",
                    "שבט",
                    "אדר",
                    "ניסן",
                    "אייר",
                    "סיוון",
                    "תמוז",
                    "אב",
                    "אלול",
                    "אדר ב'",
                ],
            },
            day_names={
                "en": [
                    "Sunday",
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                ],
                "he": [
                    "יום ראשון",
                    "יום שני",
                    "יום שלישי",
                    "יום רביעי",
                    "יום חמישי",
                    "יום שישי",
                    "שבת",
                ],
            },
            era_names={
                "en": {"after": "AM"},  # Anno Mundi
                "he": {"after": ""},
            },
            first_day_of_week=0,  # Sunday
            weekend_days=[4, 5],  # Friday, Saturday
            date_format="DD/MM/YYYY",
        ),
        CalendarSystem.BUDDHIST: CalendarConfig(
            system=CalendarSystem.BUDDHIST,
            month_names={
                "en": [
                    "January",
                    "February",
                    "March",
                    "April",
                    "May",
                    "June",
                    "July",
                    "August",
                    "September",
                    "October",
                    "November",
                    "December",
                ],
                "th": [
                    "มกราคม",
                    "กุมภาพันธ์",
                    "มีนาคม",
                    "เมษายน",
                    "พฤษภาคม",
                    "มิถุนายน",
                    "กรกฎาคม",
                    "สิงหาคม",
                    "กันยายน",
                    "ตุลาคม",
                    "พฤศจิกายน",
                    "ธันวาคม",
                ],
            },
            day_names={
                "en": [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ],
                "th": [
                    "จันทร์",
                    "อังคาร",
                    "พุธ",
                    "พฤหัสบดี",
                    "ศุกร์",
                    "เสาร์",
                    "อาทิตย์",
                ],
            },
            era_names={
                "en": {"after": "BE"},
                "th": {"after": "พ.ศ."},
            },
            first_day_of_week=6,  # Sunday
            weekend_days=[5, 6],  # Saturday, Sunday
            date_format="DD/MM/YYYY",
        ),
        CalendarSystem.NEPALI: CalendarConfig(
            system=CalendarSystem.NEPALI,
            month_names={
                "en": [
                    "Baishakh",
                    "Jestha",
                    "Ashadh",
                    "Shrawan",
                    "Bhadau",
                    "Ashwin",
                    "Kartik",
                    "Mangsir",
                    "Poush",
                    "Magh",
                    "Falgun",
                    "Chaitra",
                ],
                "ne": [
                    "बैशाख",
                    "जेष्ठ",
                    "आषाढ",
                    "श्रावण",
                    "भाद्र",
                    "आश्विन",
                    "कार्तिक",
                    "मंसिर",
                    "पौष",
                    "माघ",
                    "फाल्गुन",
                    "चैत्र",
                ],
            },
            day_names={
                "en": [
                    "Sunday",
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                ],
                "ne": [
                    "आइतबार",
                    "सोमबार",
                    "मंगलबार",
                    "बुधबार",
                    "बिहिबार",
                    "शुक्रबार",
                    "शनिबार",
                ],
            },
            era_names={
                "en": {"after": "BS"},
                "ne": {"after": "बि.सं."},
            },
            first_day_of_week=0,  # Sunday
            weekend_days=[5],  # Saturday
            date_format="YYYY/MM/DD",
        ),
    }
    # Language to preferred calendar mapping
    LANGUAGE_CALENDARS = {
        "en": CalendarSystem.GREGORIAN,
        "ar": CalendarSystem.HIJRI,
        "fa": CalendarSystem.PERSIAN,
        "ps": CalendarSystem.PERSIAN,
        "ur": CalendarSystem.HIJRI,
        "am": CalendarSystem.ETHIOPIAN,
        "ti": CalendarSystem.ETHIOPIAN,
        "he": CalendarSystem.HEBREW,
        "th": CalendarSystem.BUDDHIST,
        "ne": CalendarSystem.NEPALI,
        "cop": CalendarSystem.COPTIC,
    }

    def __init__(self) -> None:
        """Initialize calendar manager."""
        self.converters = self._init_converters()
        self.ethiopian_converter = EthiopianCalendarConverter()
        self.nepali_converter = NepaliCalendarConverter()
        self.hebrew_converter = HebrewCalendarConverter()
        self.coptic_converter = CopticCalendarConverter()

    def _init_converters(self) -> Dict:
        """Initialize calendar converters."""
        return {
            CalendarSystem.HIJRI: self._hijri_converter,
            CalendarSystem.PERSIAN: self._persian_converter,
            CalendarSystem.ETHIOPIAN: self._ethiopian_converter,
            CalendarSystem.BUDDHIST: self._buddhist_converter,
            CalendarSystem.NEPALI: self._nepali_converter,
            CalendarSystem.COPTIC: self._coptic_converter,
            CalendarSystem.HEBREW: self._hebrew_converter,
        }

    def get_preferred_calendar(self, language: str) -> CalendarSystem:
        """Get preferred calendar system for a language."""
        return self.LANGUAGE_CALENDARS.get(language, CalendarSystem.GREGORIAN)

    def convert_date(
        self,
        date_obj: Union[date, datetime],
        from_calendar: CalendarSystem,
        to_calendar: CalendarSystem,
    ) -> CalendarDate:
        """
        Convert date between calendar systems.

        Args:
            date_obj: Date to convert
            from_calendar: Source calendar system
            to_calendar: Target calendar system

        Returns:
            Converted date
        """
        if from_calendar == to_calendar:
            if isinstance(date_obj, CalendarDate):
                return date_obj
            return CalendarDate(
                year=date_obj.year,
                month=date_obj.month,
                day=date_obj.day,
                calendar_system=from_calendar,
            )

        # Convert to Gregorian first if needed
        if from_calendar != CalendarSystem.GREGORIAN:
            gregorian_date = self._to_gregorian(date_obj, from_calendar)
        else:
            gregorian_date = (
                date_obj
                if isinstance(date_obj, date)
                else date(date_obj.year, date_obj.month, date_obj.day)
            )

        # Convert from Gregorian to target
        if to_calendar != CalendarSystem.GREGORIAN:
            converter = self.converters.get(to_calendar)
            if converter:
                return cast(CalendarDate, converter(gregorian_date, to_calendar))

        return CalendarDate(
            year=gregorian_date.year,
            month=gregorian_date.month,
            day=gregorian_date.day,
            calendar_system=CalendarSystem.GREGORIAN,
        )

    def _to_gregorian(
        self, date_obj: Union[date, CalendarDate], from_calendar: CalendarSystem
    ) -> date:
        """Convert any calendar to Gregorian."""
        if isinstance(date_obj, CalendarDate):
            year, month, day = date_obj.year, date_obj.month, date_obj.day
        else:
            year, month, day = date_obj.year, date_obj.month, date_obj.day

        if from_calendar == CalendarSystem.HIJRI and Hijri:
            hijri = Hijri(year, month, day)
            greg = hijri.to_gregorian()
            return date(greg.year, greg.month, greg.day)

        elif from_calendar == CalendarSystem.PERSIAN and jdatetime:
            persian = jdatetime.date(year, month, day)
            return cast(date, persian.togregorian())

        elif from_calendar == CalendarSystem.ETHIOPIAN:
            jd = self.ethiopian_converter.ethiopian_to_jd(year, month, day)
            return self.ethiopian_converter.jd_to_gregorian(jd)

        elif from_calendar == CalendarSystem.NEPALI:
            return self.nepali_converter.bs_to_ad(year, month, day)

        elif from_calendar == CalendarSystem.COPTIC:
            jd = self.coptic_converter.coptic_to_jd(year, month, day)
            return self.ethiopian_converter.jd_to_gregorian(jd)

        elif from_calendar == CalendarSystem.HEBREW:
            # For Hebrew calendar, use approximation or external library
            # This is a simplified conversion
            jd = self.hebrew_converter.hebrew_to_jd(year, month, day)
            return self.ethiopian_converter.jd_to_gregorian(jd)

        elif from_calendar == CalendarSystem.BUDDHIST:
            # Buddhist Era is 543 years ahead
            return date(year - 543, month, day)

        return date_obj if isinstance(date_obj, date) else date(year, month, day)

    def _hijri_converter(
        self, greg_date: date, _to_calendar: CalendarSystem
    ) -> CalendarDate:
        """Convert Gregorian to Hijri."""
        if Gregorian:
            gregorian = Gregorian(greg_date.year, greg_date.month, greg_date.day)
            hijri = gregorian.to_hijri()
            return CalendarDate(
                year=hijri.year,
                month=hijri.month,
                day=hijri.day,
                calendar_system=CalendarSystem.HIJRI,
                era="AH",
            )
        else:
            logger.warning("hijri_converter library not available")
            return CalendarDate(
                year=greg_date.year,
                month=greg_date.month,
                day=greg_date.day,
                calendar_system=CalendarSystem.HIJRI,
            )

    def _persian_converter(
        self, greg_date: date, _to_calendar: CalendarSystem
    ) -> CalendarDate:
        """Convert Gregorian to Persian."""
        if jdatetime:
            persian = jdatetime.date.fromgregorian(date=greg_date)
            return CalendarDate(
                year=persian.year,
                month=persian.month,
                day=persian.day,
                calendar_system=CalendarSystem.PERSIAN,
                era="SH",
            )
        else:
            logger.warning("jdatetime library not available")
            return CalendarDate(
                year=greg_date.year,
                month=greg_date.month,
                day=greg_date.day,
                calendar_system=CalendarSystem.PERSIAN,
            )

    def _ethiopian_converter(
        self, greg_date: date, _to_calendar: CalendarSystem
    ) -> CalendarDate:
        """Convert Gregorian to Ethiopian using proper algorithm."""
        jd = self.ethiopian_converter.gregorian_to_jd(greg_date)
        year, month, day = self.ethiopian_converter.jd_to_ethiopian(jd)

        return CalendarDate(
            year=year,
            month=month,
            day=day,
            calendar_system=CalendarSystem.ETHIOPIAN,
            era="EC",
        )

    def _buddhist_converter(
        self, greg_date: date, _to_calendar: CalendarSystem
    ) -> CalendarDate:
        """Convert Gregorian to Buddhist Era."""
        # Buddhist Era is 543 years ahead of Gregorian
        return CalendarDate(
            year=greg_date.year + 543,
            month=greg_date.month,
            day=greg_date.day,
            calendar_system=CalendarSystem.BUDDHIST,
            era="BE",
        )

    def _nepali_converter(
        self, greg_date: date, _to_calendar: CalendarSystem
    ) -> CalendarDate:
        """Convert Gregorian to Nepali Bikram Sambat using lookup tables."""
        try:
            year, month, day = self.nepali_converter.ad_to_bs(greg_date)
            return CalendarDate(
                year=year,
                month=month,
                day=day,
                calendar_system=CalendarSystem.NEPALI,
                era="BS",
            )
        except ValueError as e:
            logger.error(f"Error converting to Nepali calendar: {e}")
            # Fallback to approximation
            bs_year = (
                greg_date.year + 57 if greg_date.month < 4 else greg_date.year + 56
            )
            return CalendarDate(
                year=bs_year,
                month=greg_date.month,
                day=greg_date.day,
                calendar_system=CalendarSystem.NEPALI,
                era="BS",
            )

    def _coptic_converter(
        self, greg_date: date, _to_calendar: CalendarSystem
    ) -> CalendarDate:
        """Convert Gregorian to Coptic."""
        jd = self.ethiopian_converter.gregorian_to_jd(greg_date)
        year, month, day = self.coptic_converter.jd_to_coptic(jd)

        return CalendarDate(
            year=year,
            month=month,
            day=day,
            calendar_system=CalendarSystem.COPTIC,
            era="AM",
        )

    def _hebrew_converter(
        self, greg_date: date, _to_calendar: CalendarSystem
    ) -> CalendarDate:
        """Convert Gregorian to Hebrew."""
        # This is a simplified conversion
        # In production, use a proper Hebrew calendar library like pyluach

        # Approximate conversion based on the Hebrew year starting in Sept/Oct
        year = greg_date.year + 3760
        if greg_date.month >= 9:  # After September, it's the next Hebrew year
            year += 1

        # Map Gregorian months to approximate Hebrew months
        # This is simplified and doesn't account for leap years properly
        month_mapping = {
            1: 10,  # January -> Tevet
            2: 11,  # February -> Shevat
            3: 12,  # March -> Adar
            4: 1,  # April -> Nisan
            5: 2,  # May -> Iyar
            6: 3,  # June -> Sivan
            7: 4,  # July -> Tammuz
            8: 5,  # August -> Av
            9: 6,  # September -> Elul
            10: 7,  # October -> Tishrei
            11: 8,  # November -> Cheshvan
            12: 9,  # December -> Kislev
        }

        return CalendarDate(
            year=year,
            month=month_mapping.get(greg_date.month, greg_date.month),
            day=greg_date.day,
            calendar_system=CalendarSystem.HEBREW,
            era="AM",
        )

    def format_date(
        self,
        date_obj: Union[date, CalendarDate],
        calendar_system: CalendarSystem,
        language: str,
        format_type: str = "medium",
    ) -> str:
        """
        Format date according to calendar and language.

        Args:
            date_obj: Date to format
            calendar_system: Calendar system
            language: Language code
            format_type: short, medium, long, full

        Returns:
            Formatted date string
        """
        config = self.CALENDAR_CONFIGS.get(calendar_system)
        if not config:
            return str(date_obj)

        # Get month names
        month_names = config.month_names.get(language, config.month_names.get("en", []))

        # Convert to CalendarDate if needed
        if isinstance(date_obj, date) and not isinstance(date_obj, CalendarDate):
            cal_date = self.convert_date(
                date_obj, CalendarSystem.GREGORIAN, calendar_system
            )
        else:
            cal_date = date_obj

        # Handle 13th month for Ethiopian/Coptic calendars
        if cal_date.month > len(month_names):
            month_name = month_names[-1] if month_names else str(cal_date.month)
        else:
            month_name = (
                month_names[cal_date.month - 1]
                if cal_date.month <= len(month_names)
                else str(cal_date.month)
            )

        # Format based on type
        if format_type == "short":
            return f"{cal_date.day}/{cal_date.month}/{cal_date.year}"

        elif format_type == "medium":
            return f"{cal_date.day} {month_name} {cal_date.year}"

        elif format_type == "long":
            era = config.era_names.get(language, {}).get("after", "")
            return f"{cal_date.day} {month_name} {cal_date.year} {era}".strip()

        else:  # full
            # Would include day of week in full format
            era = config.era_names.get(language, {}).get("after", "")
            return f"{cal_date.day} {month_name} {cal_date.year} {era}".strip()

    def get_month_names(
        self, calendar_system: CalendarSystem, language: str
    ) -> List[str]:
        """Get localized month names for a calendar."""
        config = self.CALENDAR_CONFIGS.get(calendar_system)
        if not config:
            return []

        return config.month_names.get(language, config.month_names.get("en", []))

    def get_day_names(
        self, calendar_system: CalendarSystem, language: str
    ) -> List[str]:
        """Get localized day names for a calendar."""
        config = self.CALENDAR_CONFIGS.get(calendar_system)
        if not config:
            return []

        return config.day_names.get(language, config.day_names.get("en", []))

    def get_date_input_config(
        self, calendar_system: CalendarSystem, language: str
    ) -> Dict[str, Any]:
        """Get configuration for date input components."""
        config = self.CALENDAR_CONFIGS.get(calendar_system)
        if not config:
            return {}

        # Get current date in the calendar system
        today = datetime.now().date()
        cal_today = self.convert_date(today, CalendarSystem.GREGORIAN, calendar_system)

        return {
            "calendar": calendar_system.value,
            "language": language,
            "firstDayOfWeek": config.first_day_of_week,
            "weekendDays": config.weekend_days,
            "monthNames": self.get_month_names(calendar_system, language),
            "dayNames": self.get_day_names(calendar_system, language),
            "today": {
                "year": cal_today.year,
                "month": cal_today.month,
                "day": cal_today.day,
            },
            "dateFormat": config.date_format,
            "direction": "rtl" if language in ["ar", "fa", "ur", "he"] else "ltr",
        }

    def calculate_age(
        self,
        birth_date: Union[date, CalendarDate],
        calendar_system: CalendarSystem,
        as_of_date: Optional[date] = None,
    ) -> Dict[str, int]:
        """
        Calculate age in years, months, days for medical records.

        Args:
            birth_date: Birth date
            calendar_system: Calendar system for calculation
            as_of_date: Calculate age as of this date (default: today)

        Returns:
            Dictionary with years, months, days
        """
        if as_of_date is None:
            as_of_date = datetime.now().date()

        # Convert both dates to the same calendar system
        if isinstance(birth_date, date) and not isinstance(birth_date, CalendarDate):
            birth_cal = self.convert_date(
                birth_date, CalendarSystem.GREGORIAN, calendar_system
            )
        else:
            birth_cal = birth_date

        current_cal = self.convert_date(
            as_of_date, CalendarSystem.GREGORIAN, calendar_system
        )

        # Calculate difference with proper month lengths
        years = current_cal.year - birth_cal.year
        months = current_cal.month - birth_cal.month
        days = current_cal.day - birth_cal.day

        # Get days in previous month for adjustment
        if days < 0:
            months -= 1
            # Get actual days in previous month
            prev_month = current_cal.month - 1 if current_cal.month > 1 else 12
            prev_year = (
                current_cal.year if current_cal.month > 1 else current_cal.year - 1
            )
            days_in_prev_month = CalendarUtils.get_days_in_month(
                prev_year, prev_month, calendar_system
            )
            days += days_in_prev_month

        if months < 0:
            years -= 1
            months += 12

        return {"years": years, "months": months, "days": days}

    def get_holidays(
        self,
        calendar_system: CalendarSystem,
        year: int,
        include_religious: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get holidays for a calendar system and year - important for medical appointments.

        Args:
            calendar_system: Calendar system
            year: Year in the calendar system
            include_religious: Include religious holidays

        Returns:
            List of holidays with dates and names
        """
        holidays = []

        if calendar_system == CalendarSystem.HIJRI:
            # Islamic holidays (dates are approximate as they depend on moon sighting)
            holidays.extend(
                [
                    {
                        "date": CalendarDate(year, 1, 1, CalendarSystem.HIJRI),
                        "name": {"en": "Islamic New Year", "ar": "رأس السنة الهجرية"},
                        "type": "religious",
                    },
                    {
                        "date": CalendarDate(year, 1, 10, CalendarSystem.HIJRI),
                        "name": {"en": "Day of Ashura", "ar": "يوم عاشوراء"},
                        "type": "religious",
                    },
                    {
                        "date": CalendarDate(year, 3, 12, CalendarSystem.HIJRI),
                        "name": {"en": "Prophet's Birthday", "ar": "المولد النبوي"},
                        "type": "religious",
                    },
                    {
                        "date": CalendarDate(year, 9, 1, CalendarSystem.HIJRI),
                        "name": {"en": "First day of Ramadan", "ar": "أول رمضان"},
                        "type": "religious",
                    },
                    {
                        "date": CalendarDate(year, 10, 1, CalendarSystem.HIJRI),
                        "name": {"en": "Eid al-Fitr", "ar": "عيد الفطر"},
                        "type": "religious",
                    },
                    {
                        "date": CalendarDate(year, 12, 10, CalendarSystem.HIJRI),
                        "name": {"en": "Eid al-Adha", "ar": "عيد الأضحى"},
                        "type": "religious",
                    },
                ]
            )

        elif calendar_system == CalendarSystem.PERSIAN:
            # Persian holidays
            holidays.extend(
                [
                    {
                        "date": CalendarDate(year, 1, 1, CalendarSystem.PERSIAN),
                        "name": {"en": "Nowruz", "fa": "نوروز"},
                        "type": "cultural",
                    },
                    {
                        "date": CalendarDate(year, 1, 13, CalendarSystem.PERSIAN),
                        "name": {"en": "Sizdah Bedar", "fa": "سیزده بدر"},
                        "type": "cultural",
                    },
                ]
            )
        elif calendar_system == CalendarSystem.ETHIOPIAN:
            # Ethiopian holidays
            holidays.extend(
                [
                    {
                        "date": CalendarDate(year, 1, 1, CalendarSystem.ETHIOPIAN),
                        "name": {"en": "Ethiopian New Year", "am": "እንቋጥጣሽ"},
                        "type": "cultural",
                    },
                    {
                        "date": CalendarDate(year, 1, 17, CalendarSystem.ETHIOPIAN),
                        "name": {"en": "Meskel", "am": "መስቀል"},
                        "type": "religious",
                    },
                    {
                        "date": CalendarDate(year, 4, 29, CalendarSystem.ETHIOPIAN),
                        "name": {"en": "Ethiopian Christmas", "am": "ገና"},
                        "type": "religious",
                    },
                    {
                        "date": CalendarDate(year, 5, 11, CalendarSystem.ETHIOPIAN),
                        "name": {"en": "Timkat (Epiphany)", "am": "ጥምቀት"},
                        "type": "religious",
                    },
                ]
            )

        elif calendar_system == CalendarSystem.NEPALI:
            # Nepali holidays
            holidays.extend(
                [
                    {
                        "date": CalendarDate(year, 1, 1, CalendarSystem.NEPALI),
                        "name": {"en": "Nepali New Year", "ne": "नयाँ वर्ष"},
                        "type": "cultural",
                    },
                ]
            )

        if not include_religious:
            holidays = [h for h in holidays if h.get("type") != "religious"]
        return holidays


# Calendar utilities
