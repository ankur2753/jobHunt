"""
ATS Adapters Package
Imports all adapter modules so they automatically register with ATSAdapterRegistry.
"""

from .base_adapter import BaseATSAdapter
from .registry import ATSAdapterRegistry
from .workday_adapter import WorkdayAdapter
from .greenhouse_adapter import GreenhouseAdapter
from .lever_adapter import LeverAdapter
from .generic_adapter import GenericATSAdapter

__all__ = [
    "BaseATSAdapter",
    "ATSAdapterRegistry",
    "WorkdayAdapter",
    "GreenhouseAdapter",
    "LeverAdapter",
    "GenericATSAdapter",
]
