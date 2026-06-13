#!/usr/bin/env python3
"""
Naukri End-to-End Auto-Apply Test Runner
Phase 2: Comprehensive validation of Naukri auto-apply workflow with diagnostics

Features:
  - Stage 1: Navigate to recommended jobs, collect job cards
  - Stage 2: For each job → click → wait for apply button
  - Stage 3: Click apply button → detect form appearance
  - Stage 4: Attempt form fill (dry-run, no submit)
  - Selector validation at each stage
  - Detailed diagnostic report

Usage:
    python scripts/tests/naukri_e2e_test.py --max-jobs 3 --dry-run --headless
    python scripts/tests/naukri_e2e_test.py --max-jobs 1 --verbose
"""

import asyncio
import argparse
import sys
import logging
import json
from pathlib import Path
from datetime import datetime

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from playwright.async_api import async_playwright
from scripts.cookie_management_login.naukri_login import NaukriPlaywright
from scripts.job_scraping.naukri_job_apply import NaukriJobApply
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.common_stuff.naukri_selector_discovery import SelectorValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NaukriE2ETestRunner:
    """End-to-end test runner for Naukri auto-apply."""
    
    def __init__(self, headless: bool = True, verbose: bool = False):
        """
        Initialize test runner.
        
        Args:
            headless: Whether to run in headless mode
            verbose: Whether to enable verbose logging
        """
        self.headless = headless
        self.verbose = verbose
        self.browser_manager = None
        self.browser = None
        self.page = None
        self.vector_db = None
        self.test_report = {
            'timestamp': datetime.now().isoformat(),
            'stages': {},
            'results': {}
        }
    
    async def setup(self) -> None:
        """Setup browser and dependencies."""
        logger.info("🔧 Setting up Naukri E2E test environment...")
        
        # Initialize vector DB
        self.vector_db = VectorDBManager()
        logger.info("✓ Vector DB initialized")
        
        # Setup browser manager
        self.browser_manager = NaukriPlaywright()
        await self.browser_manager.setup_driver(headless=self.headless)
        self.page = self.browser_manager.page
        logger.info("✓ Browser setup complete")
        
        # Check login
        if not await self.browser_manager.is_logged_in():
            logger.error("❌ Not logged into Naukri")
            raise RuntimeError("Please log into Naukri first")
        
        logger.info("✓ Logged into Naukri")
    
    async def run_test(self, max_jobs: int = 3) -> dict:
        """
        Run complete E2E test.
        
        Args:
            max_jobs: Maximum jobs to test
        
        Returns:
            Test report dictionary
        """
        try:
            await self.setup()
            
            # Stage 1: Navigate and collect job cards
            stage_1_result = await self._stage_1_navigate_and_collect()
            self.test_report['stages']['stage_1'] = stage_1_result
            
            if not stage_1_result['success']:
                logger.error("❌ Stage 1 failed - cannot proceed")
                return self.test_report
            
            job_cards_count = stage_1_result['job_cards_found']
            logger.info(f"\n✅ Stage 1 complete: {job_cards_count} job cards found")
            
            # Stage 2: Process job cards and validate apply buttons
            stage_2_result = await self._stage_2_validate_job_cards(
                max_jobs=min(max_jobs, job_cards_count)
            )
            self.test_report['stages']['stage_2'] = stage_2_result
            
            logger.info(f"\n✅ Stage 2 complete: {stage_2_result['jobs_processed']} jobs processed")
            
            # Stage 3: Click apply and detect form
            stage_3_result = await self._stage_3_apply_and_detect_form()
            self.test_report['stages']['stage_3'] = stage_3_result
            
            logger.info(f"\n✅ Stage 3 complete: {stage_3_result['forms_detected']} forms detected")
            
            # Summary
            self._print_report()
            
            return self.test_report
        
        except Exception as e:
            logger.error(f"❌ Test failed: {str(e)}", exc_info=True)
            self.test_report['error'] = str(e)
            return self.test_report
        
        finally:
            await self.cleanup()
    
    async def _stage_1_navigate_and_collect(self) -> dict:
        """
        Stage 1: Navigate to recommended jobs and collect job cards.
        
        Returns:
            Stage result dictionary
        """
        logger.info("\n" + "="*70)
        logger.info("📋 STAGE 1: Navigate to Recommended Jobs & Collect Job Cards")
        logger.info("="*70)
        
        result = {
            'success': False,
            'job_cards_found': 0,
            'url': None,
            'selectors_validated': False,
            'errors': []
        }
        
        try:
            # Navigate to recommended jobs
            url = "https://www.naukri.com/mnjuser/recommendedjobs"
            logger.info(f"📍 Navigating to: {url}")
            await self.page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)
            
            result['url'] = self.page.url
            
            # Validate selectors
            logger.info("\n🔍 Validating selectors on recommended jobs page...")
            validator = SelectorValidator(self.page, enable_logging=True)
            await validator.validate_all_selectors()
            validator.print_summary()
            
            result['selectors_validated'] = True
            
            # Collect job cards
            logger.info("\n📇 Collecting job cards...")
            selector = '[data-qa="jobTuple"], .jobTuple, .srp-jobtuple, .jobCardContainer, [data-qa="job-card"]'
            job_cards = await self.page.query_selector_all(selector)
            
            logger.info(f"✅ Found {len(job_cards)} job cards")
            result['job_cards_found'] = len(job_cards)
            result['success'] = True
            
        except Exception as e:
            logger.error(f"❌ Stage 1 failed: {str(e)}")
            result['errors'].append(str(e))
        
        return result
    
    async def _stage_2_validate_job_cards(self, max_jobs: int = 3) -> dict:
        """
        Stage 2: Validate job card elements and apply buttons.
        
        Args:
            max_jobs: Maximum jobs to validate
        
        Returns:
            Stage result dictionary
        """
        logger.info("\n" + "="*70)
        logger.info(f"📋 STAGE 2: Validate Job Cards (Testing {max_jobs} jobs)")
        logger.info("="*70)
        
        result = {
            'jobs_processed': 0,
            'jobs_with_apply_button': 0,
            'job_details': [],
            'errors': []
        }
        
        try:
            selector = '[data-qa="jobTuple"], .jobTuple, .srp-jobtuple, .jobCardContainer, [data-qa="job-card"]'
            job_cards = await self.page.query_selector_all(selector)
            jobs_to_test = min(max_jobs, len(job_cards))
            
            for idx, job_card in enumerate(job_cards[:jobs_to_test], 1):
                try:
                    logger.info(f"\n  [{idx}/{jobs_to_test}] Validating job card...")
                    
                    # Extract job title
                    title_elem = await job_card.query_selector('[data-qa="jobTitle"], .jobTitle, a.title')
                    job_title = await title_elem.text_content() if title_elem else "Unknown"
                    logger.info(f"  Job Title: {job_title}")
                    
                    # Check for apply button
                    apply_button = await job_card.query_selector('button[data-qa="nxtApplyBtn"], button[data-qa="applyBtn"], button:has-text("Apply")')
                    has_apply_button = apply_button is not None
                    
                    if has_apply_button:
                        is_visible = await apply_button.is_visible()
                        is_enabled = await apply_button.is_enabled()
                        logger.info(f"  Apply Button: ✅ Found (Visible: {is_visible}, Enabled: {is_enabled})")
                        if is_visible and is_enabled:
                            result['jobs_with_apply_button'] += 1
                    else:
                        logger.warning(f"  Apply Button: ❌ Not found")
                    
                    result['job_details'].append({
                        'index': idx,
                        'title': job_title,
                        'has_apply_button': has_apply_button
                    })
                    
                    result['jobs_processed'] += 1
                
                except Exception as e:
                    logger.error(f"  Error validating job {idx}: {str(e)}")
                    result['errors'].append({
                        'job_index': idx,
                        'error': str(e)
                    })
        
        except Exception as e:
            logger.error(f"❌ Stage 2 failed: {str(e)}")
            result['errors'].append(str(e))
        
        return result
    
    async def _stage_3_apply_and_detect_form(self) -> dict:
        """
        Stage 3: Click apply button and detect form appearance.
        
        Returns:
            Stage result dictionary
        """
        logger.info("\n" + "="*70)
        logger.info("📋 STAGE 3: Test Apply Button & Form Detection (First Job)")
        logger.info("="*70)
        
        result = {
            'success': False,
            'forms_detected': 0,
            'form_elements_found': 0,
            'selectors_validated': False,
            'errors': []
        }
        
        try:
            # Get first job card
            selector = '[data-qa="jobTuple"], .jobTuple, .srp-jobtuple, .jobCardContainer, [data-qa="job-card"]'
            job_cards = await self.page.query_selector_all(selector)
            if not job_cards:
                raise ValueError("No job cards found")
            
            job_card = job_cards[0]
            
            # Click on job card
            logger.info("Clicking first job card...")
            
            # Naukri opens job details in a new tab. We must capture the new page.
            async with self.page.context.expect_page() as new_page_info:
                await job_card.click()
            
            new_page = await new_page_info.value
            await new_page.wait_for_load_state('domcontentloaded')
            logger.info(f"Navigated to new tab: {new_page.url}")
            
            # Read and log the DOM content before clicking apply (as requested)
            # dom_content = await new_page.content()
            # logger.debug(f"DOM Content snippet (first 1000 chars): {dom_content[:1000]}")
            
            # Try to click apply button
            apply_button = await new_page.query_selector('button[data-qa="nxtApplyBtn"], button[data-qa="applyBtn"], button:has-text("Apply")')
            
            if apply_button:
                logger.info("Clicking apply button...")
                await apply_button.click()
                await asyncio.sleep(3)  # Wait for form to load
                
                # Validate selectors on form page
                logger.info("\n🔍 Validating selectors on form page...")
                validator = SelectorValidator(new_page, enable_logging=True)
                await validator.validate_all_selectors()
                validator.print_summary()
                result['selectors_validated'] = True
                
                # Check for form container
                form_containers = await new_page.query_selector_all(
                    '.filler-container, .customFields, [data-qa="customFields"]'
                )
                
                if form_containers:
                    result['forms_detected'] = len(form_containers)
                    logger.info(f"✅ Found {len(form_containers)} form container(s)")
                    result['success'] = True
                    
                    # Count form fields
                    all_fields = await new_page.query_selector_all(
                        'input, select, textarea, [role="combobox"], [role="radio"]'
                    )
                    result['form_elements_found'] = len(all_fields)
                    logger.info(f"✅ Found {len(all_fields)} form element(s)")
                else:
                    logger.warning("⚠️  No form container found - form may still be loading")
                    result['errors'].append("Form container not detected after apply click")
                
                # Close the new tab
                await new_page.close()
            else:
                raise ValueError("Apply button not found")
        
        except Exception as e:
            logger.error(f"❌ Stage 3 failed: {str(e)}")
            result['errors'].append(str(e))
        
        return result
    
    def _print_report(self) -> None:
        """Print detailed test report."""
        print("\n" + "="*70)
        print("📊 NAUKRI E2E TEST REPORT")
        print("="*70)
        
        if 'error' in self.test_report:
            print(f"\n❌ Test Failed: {self.test_report['error']}")
            return
        
        stages = self.test_report.get('stages', {})
        
        for stage_name, stage_data in stages.items():
            success = stage_data.get('success', False)
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"\n{status} | {stage_name.upper()}")
            
            # Print stage-specific metrics
            if stage_name == 'stage_1':
                print(f"   Job cards found: {stage_data.get('job_cards_found', 0)}")
            elif stage_name == 'stage_2':
                print(f"   Jobs processed: {stage_data.get('jobs_processed', 0)}")
                print(f"   Jobs with apply button: {stage_data.get('jobs_with_apply_button', 0)}")
            elif stage_name == 'stage_3':
                print(f"   Forms detected: {stage_data.get('forms_detected', 0)}")
                print(f"   Form elements found: {stage_data.get('form_elements_found', 0)}")
            
            # Print errors if any
            errors = stage_data.get('errors', [])
            if errors:
                print(f"   Errors: {len(errors)}")
                for error in errors:
                    error_msg = error if isinstance(error, str) else error.get('error', str(error))
                    print(f"     - {error_msg}")
        
        print("\n" + "="*70)
    
    async def cleanup(self) -> None:
        """Cleanup browser and resources."""
        if self.browser_manager and self.browser_manager.browser:
            await self.browser_manager.browser.close()
            logger.info("✓ Browser closed")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Naukri E2E Test Runner')
    parser.add_argument('--max-jobs', type=int, default=3, help='Maximum jobs to test (default: 3)')
    parser.add_argument('--headless', action='store_true', default=True, help='Run in headless mode')
    parser.add_argument('--headed', dest='headless', action='store_false', help='Run in headed mode (show browser)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    runner = NaukriE2ETestRunner(headless=args.headless, verbose=args.verbose)
    report = await runner.run_test(max_jobs=args.max_jobs)
    
    # Export report
    report_path = Path(__file__).parent.parent.parent / 'logs' / f'naukri_e2e_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"📄 Test report saved: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
