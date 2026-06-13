"""
Answer Validation and Normalization Module

Handles field-type specific validation, formatting, and normalization of answers
extracted from the vector DB before filling form fields.
"""

import re
from typing import Optional, Dict
from enum import Enum


class FieldCategory(Enum):
    """Categories for different types of form fields."""
    SALARY = "salary"
    LOCATION = "location"
    EXPERIENCE = "experience"
    NOTICE_PERIOD = "notice_period"
    AVAILABILITY = "availability"
    CONTACT = "contact"
    TEXT = "text"
    DATE = "date"
    NUMBER = "number"
    BOOLEAN = "boolean"


class AnswerNormalizer:
    """Normalize answers based on expected format and field category."""
    
    # Salary-related keywords and patterns
    SALARY_KEYWORDS = ['salary', 'ctc', 'lpa', 'lakhs', 'salary package', 'compensation', 'pay', 'wage']
    
    # Location-related keywords
    LOCATION_KEYWORDS = ['location', 'city', 'area', 'place', 'work location', 'office', 'remote']
    
    # Experience-related keywords
    EXPERIENCE_KEYWORDS = ['experience', 'years of experience', 'exp', 'work experience', 'prior experience']
    
    # Notice period keywords
    NOTICE_KEYWORDS = ['notice', 'notice period', 'notice days', 'joining', 'available', 'start']
    
    # Availability keywords
    AVAILABILITY_KEYWORDS = ['available', 'availability', 'ready', 'can start', 'joining date']
    
    @staticmethod
    def normalize_salary(value: str) -> Optional[str]:
        """
        Normalize salary values to standard format.
        
        Examples:
            "12-15 LPA" -> "12-15"
            "12 lakhs" -> "12"
            "1200000" -> "12" (per year assumption)
        
        Args:
            value: Raw salary value
        
        Returns:
            Normalized salary (number or range) or None if invalid
        """
        if not value:
            return None
        
        value = str(value).strip().upper()
        
        # Pattern: "12-15 LPA", "12-15 Lakhs", etc.
        match = re.search(r'(\d+(?:\.\d+)?)\s*-?\s*(\d+(?:\.\d+)?)?.*?(LPA|LAKHS|PA|P\.A\.)?', value)
        if match:
            lower = match.group(1)
            upper = match.group(2)
            if upper:
                return f"{lower}-{upper}"
            return lower
        
        # Pattern: Just a number (assume it's in lakhs)
        match = re.search(r'^\d+(?:\.\d+)?$', value.strip())
        if match:
            return value.strip()
        
        return None

    @staticmethod
    def normalize_location(value: str) -> Optional[str]:
        """
        Normalize location values.
        
        Examples:
            "Bangalore, India" -> "Bangalore"
            "Remote (Work from home)" -> "Remote"
            "Multiple cities" -> "Multiple"
        
        Args:
            value: Raw location value
        
        Returns:
            Normalized location or None if invalid
        """
        if not value:
            return None
        
        value = str(value).strip()
        
        # Handle common location patterns
        if value.lower() in ['remote', 'work from home', 'wfh', 'online']:
            return "Remote"
        
        # Extract first city before comma
        if ',' in value:
            value = value.split(',')[0].strip()
        
        # Handle "Multiple" or similar
        if value.lower() in ['multiple', 'multiple cities', 'various', 'any', 'all']:
            return "Multiple"
        
        # Remove common suffixes
        value = re.sub(r',\s*India\s*$', '', value, flags=re.IGNORECASE)
        
        return value.strip() if value.strip() else None

    @staticmethod
    def normalize_experience(value: str) -> Optional[str]:
        """
        Normalize experience values to years.
        
        Examples:
            "5 years" -> "5"
            "5.2 years" -> "5.2"
            "60 months" -> "5"
            "2-3 years" -> "2-3"
        
        Args:
            value: Raw experience value
        
        Returns:
            Normalized experience (years) or None if invalid
        """
        if not value:
            return None
        
        value = str(value).strip().lower()
        
        # Pattern: X-Y years (range)
        match = re.search(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*years?', value)
        if match:
            return f"{match.group(1)}-{match.group(2)}"
        
        # Pattern: X months (convert to years)
        match = re.search(r'(\d+(?:\.\d+)?)\s*months?', value)
        if match:
            months = float(match.group(1))
            years = months / 12
            return f"{years:.1f}"
        
        # Pattern: X years
        match = re.search(r'(\d+(?:\.\d+)?)\s*years?', value)
        if match:
            return match.group(1)
        
        # Just a number (assume years)
        match = re.search(r'^(\d+(?:\.\d+)?)$', value)
        if match:
            return match.group(1)
        
        return None

    @staticmethod
    def normalize_notice_period(value: str) -> Optional[str]:
        """
        Normalize notice period values to days.
        
        Examples:
            "30 days" -> "30"
            "2 weeks" -> "14"
            "1 month" -> "30"
            "Immediate" -> "0"
        
        Args:
            value: Raw notice period value
        
        Returns:
            Normalized notice period (days) or None if invalid
        """
        if not value:
            return None
        
        value = str(value).strip().lower()
        
        # Handle immediate/no notice
        if value in ['immediate', 'now', '0', 'current']:
            return "0"
        
        # Pattern: X days
        match = re.search(r'(\d+)\s*days?', value)
        if match:
            return match.group(1)
        
        # Pattern: X weeks (convert to days)
        match = re.search(r'(\d+)\s*weeks?', value)
        if match:
            days = int(match.group(1)) * 7
            return str(days)
        
        # Pattern: X months (convert to days, assuming 30 days per month)
        match = re.search(r'(\d+)\s*months?', value)
        if match:
            days = int(match.group(1)) * 30
            return str(days)
        
        return None

    @staticmethod
    def normalize_availability(value: str) -> Optional[str]:
        """
        Normalize availability/joining date values.
        
        Examples:
            "Can join in 2 weeks" -> "14 days"
            "Immediate" -> "Immediate"
            "2024-01-15" -> "2024-01-15"
        
        Args:
            value: Raw availability value
        
        Returns:
            Normalized availability or None if invalid
        """
        if not value:
            return None
        
        value = str(value).strip().lower()
        
        # Handle immediate
        if value in ['immediate', 'asap', 'now', 'can join immediately']:
            return "Immediate"
        
        # Handle date pattern (YYYY-MM-DD)
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', value)
        if date_match:
            return date_match.group(0)
        
        # Handle "X weeks/days" patterns
        weeks_match = re.search(r'(\d+)\s*weeks?', value)
        if weeks_match:
            days = int(weeks_match.group(1)) * 7
            return f"{days} days" if days > 1 else f"{days} day"
        
        days_match = re.search(r'(\d+)\s*days?', value)
        if days_match:
            days = days_match.group(1)
            return f"{days} days" if int(days) > 1 else f"{days} day"
        
        return value if value else None

    @staticmethod
    def normalize_email(value: str) -> Optional[str]:
        """
        Validate and normalize email addresses.
        
        Args:
            value: Raw email value
        
        Returns:
            Valid email or None if invalid
        """
        if not value:
            return None
        
        value = str(value).strip().lower()
        
        # Simple email validation
        if re.match(r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$', value):
            return value
        
        return None

    @staticmethod
    def normalize_phone(value: str) -> Optional[str]:
        """
        Validate and normalize phone numbers.
        
        Args:
            value: Raw phone number
        
        Returns:
            Normalized phone or None if invalid
        """
        if not value:
            return None
        
        value = str(value).strip()
        
        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\.\(\)\+]', '', value)
        
        # Check if it's a valid phone (10-15 digits)
        if re.match(r'^\d{10,15}$', cleaned):
            return cleaned
        
        return None

    @staticmethod
    def normalize_date(value: str, target_format: str = "YYYY-MM-DD") -> Optional[str]:
        """
        Normalize date values to a standard format.
        
        Args:
            value: Raw date value
            target_format: Target format (default: "YYYY-MM-DD")
        
        Returns:
            Normalized date or None if invalid
        """
        if not value:
            return None
        
        value = str(value).strip()
        
        # Already in YYYY-MM-DD format
        if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
            return value
        
        # Try common formats
        date_patterns = [
            (r'^(\d{4})[/-](\d{2})[/-](\d{2})$', r'\1-\2-\3'),  # YYYY-MM-DD or YYYY/MM/DD
            (r'^(\d{2})[/-](\d{2})[/-](\d{4})$', r'\3-\2-\1'),  # DD-MM-YYYY or MM-DD-YYYY (ambiguous)
            (r'^(\d{1,2})\s+\w+\s+(\d{4})$', None),  # "15 Jan 2024" (would need month mapping)
        ]
        
        for pattern, replacement in date_patterns:
            match = re.match(pattern, value)
            if match and replacement:
                return re.sub(pattern, replacement, value)
        
        return None

    @staticmethod
    def normalize_boolean(value: str) -> Optional[bool]:
        """
        Normalize boolean-like values.
        
        Args:
            value: Raw value
        
        Returns:
            True, False, or None if ambiguous
        """
        if not value:
            return None
        
        value = str(value).strip().lower()
        
        if value in ['yes', 'true', '1', 'checked', 'on', 'enabled']:
            return True
        elif value in ['no', 'false', '0', 'unchecked', 'off', 'disabled']:
            return False
        
        return None

    @staticmethod
    def get_field_category(question: str) -> FieldCategory:
        """
        Infer field category from question text.
        
        Args:
            question: Question text
        
        Returns:
            Best matching FieldCategory
        """
        question_lower = question.lower()
        
        # Check for category keywords
        if any(k in question_lower for k in AnswerNormalizer.SALARY_KEYWORDS):
            return FieldCategory.SALARY
        elif any(k in question_lower for k in AnswerNormalizer.LOCATION_KEYWORDS):
            return FieldCategory.LOCATION
        elif any(k in question_lower for k in AnswerNormalizer.EXPERIENCE_KEYWORDS):
            return FieldCategory.EXPERIENCE
        elif any(k in question_lower for k in AnswerNormalizer.NOTICE_KEYWORDS):
            return FieldCategory.NOTICE_PERIOD
        elif any(k in question_lower for k in AnswerNormalizer.AVAILABILITY_KEYWORDS):
            return FieldCategory.AVAILABILITY
        elif 'email' in question_lower or 'mail' in question_lower:
            return FieldCategory.CONTACT
        elif 'phone' in question_lower or 'mobile' in question_lower:
            return FieldCategory.CONTACT
        elif 'date' in question_lower or 'when' in question_lower:
            return FieldCategory.DATE
        elif any(c in question_lower for c in ['number', 'count', 'how many', 'quantity']):
            return FieldCategory.NUMBER
        elif any(c in question_lower for c in ['yes', 'no', 'willing', 'interested', 'agree']):
            return FieldCategory.BOOLEAN
        
        return FieldCategory.TEXT

    @staticmethod
    def normalize(value: str, field_category: FieldCategory) -> Optional[str]:
        """
        Normalize value based on field category.
        
        Args:
            value: Raw value
            field_category: Category of the field
        
        Returns:
            Normalized value or None if invalid
        """
        normalizers = {
            FieldCategory.SALARY: AnswerNormalizer.normalize_salary,
            FieldCategory.LOCATION: AnswerNormalizer.normalize_location,
            FieldCategory.EXPERIENCE: AnswerNormalizer.normalize_experience,
            FieldCategory.NOTICE_PERIOD: AnswerNormalizer.normalize_notice_period,
            FieldCategory.AVAILABILITY: AnswerNormalizer.normalize_availability,
            FieldCategory.CONTACT: AnswerNormalizer.normalize_email,  # Try email first
            FieldCategory.DATE: AnswerNormalizer.normalize_date,
            FieldCategory.TEXT: lambda x: x.strip() if x else None,
            FieldCategory.NUMBER: lambda x: re.search(r'\d+', x).group(0) if x and re.search(r'\d+', x) else None,
            FieldCategory.BOOLEAN: lambda x: str(AnswerNormalizer.normalize_boolean(x)).lower(),
        }
        
        normalizer = normalizers.get(field_category)
        if normalizer:
            return normalizer(value)
        
        return value.strip() if value else None
