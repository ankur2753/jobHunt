"""
Unit Test Suite for ATS Adapter Registry and Extensible Adapters
Verifies URL pattern matching, adapter discovery, and registration.
"""

import unittest
import asyncio
from scripts.applying_to_portals.ats_adapters import (
    ATSAdapterRegistry,
    WorkdayAdapter,
    GreenhouseAdapter,
    LeverAdapter,
    GenericATSAdapter,
)


class TestATSAdapterRegistry(unittest.TestCase):

    def test_registered_adapters(self):
        registered = ATSAdapterRegistry.list_registered_adapters()
        self.assertIn("Workday", registered)
        self.assertIn("Greenhouse", registered)
        self.assertIn("Lever", registered)
        self.assertIn("Generic ATS", registered)

    def test_workday_url_matching(self):
        url = "https://nvidia.wd1.myworkdayjobs.com/NVIDIAExternalCareerSite/job/USA-CA-Santa-Clara/Software-Engineer_JR19827"
        self.assertTrue(WorkdayAdapter.can_handle(url))
        self.assertFalse(GreenhouseAdapter.can_handle(url))
        self.assertFalse(LeverAdapter.can_handle(url))

    def test_greenhouse_url_matching(self):
        url = "https://boards.greenhouse.io/stripe/jobs/4819283"
        self.assertTrue(GreenhouseAdapter.can_handle(url))
        self.assertFalse(WorkdayAdapter.can_handle(url))

    def test_lever_url_matching(self):
        url = "https://jobs.lever.co/netflix/92839182-1293-4812"
        self.assertTrue(LeverAdapter.can_handle(url))
        self.assertFalse(WorkdayAdapter.can_handle(url))

    def test_generic_fallback_matching(self):
        url = "https://careers.somecustomcompany.com/openings/123"
        self.assertFalse(WorkdayAdapter.can_handle(url))
        self.assertFalse(GreenhouseAdapter.can_handle(url))
        self.assertFalse(LeverAdapter.can_handle(url))
        self.assertTrue(GenericATSAdapter.can_handle(url))

    def test_get_adapter_dispatch(self):
        async def run_async_test():
            workday_url = "https://adobe.wd5.myworkdayjobs.com/external/job/123"
            adapter = await ATSAdapterRegistry.get_adapter(page=None, url=workday_url)
            self.assertEqual(adapter.adapter_name(), "Workday")

            lever_url = "https://jobs.lever.co/figma/abc"
            adapter = await ATSAdapterRegistry.get_adapter(page=None, url=lever_url)
            self.assertEqual(adapter.adapter_name(), "Lever")

            generic_url = "https://careers.acme.org/job/456"
            adapter = await ATSAdapterRegistry.get_adapter(page=None, url=generic_url)
            self.assertEqual(adapter.adapter_name(), "Generic ATS")

        asyncio.run(run_async_test())


if __name__ == "__main__":
    unittest.main()
