"""
Naukri Job Auto-Apply Integration
Automatically applies to recommended jobs on Naukri and fills forms using chatbot form filler
Includes human fallback and pattern learning capabilities
Phase 1+: Integrated selector discovery and validation logging
"""

import asyncio
import logging
import json
from typing import List, Dict, Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from pathlib import Path
import sys
from datetime import datetime, timedelta

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.cookie_management_login.naukri_form_filler import NaukriFormFiller
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.common_stuff.pattern_learner import PatternLearner, HumanFallbackHandler
from scripts.common_stuff.naukri_selector_discovery import SelectorValidator
from scripts.common_stuff.retry_utils import retry_async, retry_until_visible

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NaukriJobApply:
    """Automatically applies to Naukri recommended jobs and fills forms."""
    
    RECOMMENDED_JOBS_URL = "https://www.naukri.com/mnjuser/recommendedjobs"
    
    SELECTORS = {
        'job_cards': '[data-qa="jobTuple"], .jobTuple, .srp-jobtuple, .jobCardContainer, [data-qa="job-card"]',
        'job_card_title': '[data-qa="jobTitle"], .jobTitle, a.title, .title, h2, h3',
        'apply_button': 'button[data-qa="nxtApplyBtn"], button[data-qa="applyBtn"], button:has-text("Apply")',
        'job_url': 'a[data-qa="jobCardCurrentJobTitle"]',
        'loader': '.loader, [data-qa="loader"]',
        'popup_close': 'button[aria-label="Close"], .popup-close, [data-qa="closeModal"]',
    }
    
    # New selectors for bulk select workflow (Phase 2)
    BULK_SELECT_SELECTORS = {
        'job_card_checkbox': '.tuple-check-box, input[type="checkbox"]',  # Checkbox within job card
        'job_card_select_btn': 'button[data-qa*="select"], button[aria-label*="select"]',  # Select button
        'bulk_apply_button': 'button[data-qa="applyBtn"], button[data-qa="nxtApplyBtn"], button:has-text("Apply")',  # Top right apply
        'selected_jobs_count': '[data-qa="selectedCount"], [class*="selected"]',  # Counter for selected jobs
    }
    
    def __init__(self, page: Page, vector_db_manager: VectorDBManager = None, enable_selector_validation: bool = True):
        """
        Initialize Naukri job applicator.
        
        Args:
            page: Playwright page object (assumed to be logged into Naukri)
            vector_db_manager: VectorDBManager for form filling (will initialize if None)
            enable_selector_validation: Whether to validate selectors on startup
        """
        self.page = page
        self.vector_db = vector_db_manager or VectorDBManager()
        self.jobs_applied = 0
        self.jobs_failed = 0
        self.applied_job_ids = set()
        
        # Initialize selector validator for diagnostics
        self.selector_validator = SelectorValidator(page, enable_logging=True) if enable_selector_validation else None
        self.selector_validation_report = None
        
        # Initialize pattern learning
        self.pattern_learner = PatternLearner()
        self.human_fallback = HumanFallbackHandler(page, self.pattern_learner)
        self.enable_human_fallback = True  # Can be set to False for fully automated mode
        
        # Track selected jobs for bulk apply
        self.selected_job_cards = []
        self.selected_job_titles = []
    
    async def select_jobs_bulk(self, max_jobs: int = 5) -> List[Dict[str, str]]:
        """
        Select multiple jobs at once before bulk apply (Phase 2).
        
        Args:
            max_jobs: Maximum number of jobs to select (default: 5)
        
        Returns:
            List of dictionaries containing job_title, company_name, job_url
        """
        selected_jobs = []
        
        try:
            logger.info(f"\n🔄 Starting bulk job selection (max {max_jobs})...")
            
            # Get all job cards
            job_cards = await self.page.query_selector_all(self.SELECTORS['job_cards'])
            logger.info(f"Found {len(job_cards)} total job cards")
            
            if not job_cards:
                logger.warning("No job cards found on the page")
                return selected_jobs
            
            jobs_to_select = min(max_jobs, len(job_cards))
            logger.info(f"Will select {jobs_to_select} jobs")
            
            # Try to find checkbox-based selection first
            first_card = job_cards[0]
            checkbox = await first_card.query_selector(self.BULK_SELECT_SELECTORS['job_card_checkbox'])
            select_btn = await first_card.query_selector(self.BULK_SELECT_SELECTORS['job_card_select_btn'])
            
            # Determine selection method
            selection_method = None
            if checkbox:
                selection_method = 'checkbox'
                logger.info("📋 Using checkbox-based selection")
            elif select_btn:
                selection_method = 'button'
                logger.info("📋 Using button-based selection")
            else:
                logger.warning("⚠️  Could not detect selection UI. Will fall back to direct apply.")
                return selected_jobs
            
            # Select jobs one by one
            for idx, job_card in enumerate(job_cards[:jobs_to_select], 1):
                try:
                    await job_card.scroll_into_view_if_needed()
                    await asyncio.sleep(0.3)
                    
                    # Extract job title
                    job_title = await self._extract_text(job_card, self.SELECTORS['job_card_title'])
                    if not job_title or job_title == "Unknown Job":
                        title_elem = await job_card.query_selector('a.title, [data-qa="jobTitle"]')
                        if title_elem:
                            job_title = (await title_elem.inner_text()).strip()
                    
                    # Extract company name
                    company_name = "Unknown Company"
                    company_elem = await job_card.query_selector('.companyName, [data-qa="companyName"], [data-qa="jobCardCompanyName"], [class*="company"]')
                    if company_elem:
                        company_name = (await company_elem.inner_text()).strip()
                    
                    # Extract job URL
                    job_url = ""
                    url_elem = await job_card.query_selector('a[href*="/jobs/"], a.title, a[data-qa="jobCardCurrentJobTitle"], a')
                    if url_elem:
                        href = await url_elem.get_attribute('href')
                        if href:
                            if href.startswith('/'):
                                job_url = f"https://www.naukri.com{href}"
                            else:
                                job_url = href
                    
                    # Click checkbox or select button
                    if selection_method == 'checkbox':
                        selection_element = await job_card.query_selector(self.BULK_SELECT_SELECTORS['job_card_checkbox'])
                    else:
                        selection_element = await job_card.query_selector(self.BULK_SELECT_SELECTORS['job_card_select_btn'])
                    
                    if selection_element:
                        is_visible = await selection_element.is_visible()
                        if not is_visible:
                            await selection_element.scroll_into_view_if_needed()
                            await asyncio.sleep(0.2)
                        
                        await selection_element.click()
                        await asyncio.sleep(0.5)  # Wait for selection to register
                        
                        # Verify selection
                        if selection_method == 'checkbox':
                            try:
                                is_checked = await selection_element.is_checked()
                                logger.info(f"      ✅ Selected (checked={is_checked}): {job_title}")
                            except Exception:
                                logger.info(f"      ✅ Selected: {job_title}")
                        else:
                            logger.info(f"      ✅ Selected: {job_title}")
                        
                        self.selected_job_cards.append(job_card)
                        self.selected_job_titles.append(job_title)
                        
                        selected_jobs.append({
                            'job_title': job_title,
                            'company_name': company_name,
                            'job_url': job_url
                        })
                        
                    else:
                        logger.warning(f"      ❌ Selection element not found for: {job_title}")
                
                except Exception as e:
                    logger.error(f"  Error selecting job {idx}: {str(e)}")
            
            logger.info(f"\n✅ Selected {len(selected_jobs)} jobs for bulk apply")
            
        except Exception as e:
            logger.error(f"Error during bulk selection: {str(e)}")
        
        return selected_jobs
    
    async def click_bulk_apply_button(self) -> dict:
        """
        Find and click the bulk apply button (usually top right corner).
        
        Returns:
            Dictionary with button click results
        """
        result = {
            'success': False,
            'button_found': False,
            'button_selector': None,
            'errors': []
        }
        
        try:
            logger.info("\n🔍 Looking for bulk apply button...")
            
            # Wait a moment for selection UI to stabilize
            await asyncio.sleep(1)
            
            # Try multiple selectors for the apply button
            button_selectors = [
                'button[data-qa="nxtApplyBtn"]',
                'button[data-qa="applyBtn"]',
                'button:has-text("Apply")',
                self.BULK_SELECT_SELECTORS['bulk_apply_button']
            ]
            
            apply_button = None
            found_selector = None
            
            for selector in button_selectors:
                try:
                    buttons = await self.page.query_selector_all(selector)
                    for btn in buttons:
                        is_visible = await btn.is_visible()
                        is_enabled = await btn.is_enabled()
                        
                        if is_visible and is_enabled:
                            apply_button = btn
                            found_selector = selector
                            logger.info(f"✅ Found apply button with selector: {selector}")
                            break
                    
                    if apply_button:
                        break
                except:
                    continue
            
            if apply_button:
                result['button_found'] = True
                result['button_selector'] = found_selector
                
                # Scroll into view if needed
                bbox = await apply_button.bounding_box()
                if bbox:
                    viewport_width = await self.page.evaluate('window.innerWidth')
                    is_right_aligned = bbox['x'] > viewport_width * 0.7
                    logger.info(f"📍 Button location: x={bbox['x']}, y={bbox['y']}, right_aligned={is_right_aligned}")
                
                if not await apply_button.is_visible():
                    await apply_button.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                
                logger.info("👆 Clicking bulk apply button...")
                await apply_button.click()
                await asyncio.sleep(2)  # Wait for response
                
                result['success'] = True
                logger.info("✅ Bulk apply button clicked successfully")
                
            else:
                logger.warning("⚠️  Bulk apply button not found in common locations")
                result['errors'].append("Apply button not found")
        
        except Exception as e:
            logger.error(f"Error clicking bulk apply button: {str(e)}")
            result['errors'].append(str(e))
        
        return result

    async def update_last_working_day(self, days_offset: int = 60) -> bool:
        """
        Updates the expected last working day on Naukri profile page to current date + days_offset.
        
        Args:
            days_offset: Number of days from today for LWD (default: 60)
            
        Returns:
            bool: True if updated successfully, False otherwise.
        """
        try:
            profile_url = "https://www.naukri.com/mnjuser/profile"
            
            # 1. Calculate target LWD
            target_date = datetime.now() + timedelta(days=days_offset)
            year = target_date.year
            month_num = target_date.month
            day = target_date.day
            month_name = target_date.strftime("%b")
            
            logger.info(f"Navigating to Naukri profile page to update LWD: {profile_url}")
            await self.page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(3000)
            
            logger.info(f"Target LWD computed: {day} {month_name} {year} (month code: {month_num})")
            
            # 2. Click the edit profile basic details button
            edit_btn_selector = ".hdn .icon.edit"
            logger.info("Opening Basic Details drawer...")
            edit_btn = await self.page.wait_for_selector(edit_btn_selector, timeout=10000)
            await edit_btn.click()
            
            # 3. Wait for the form and async elements (pre-loaders) to load completely
            form_selector = "#editBasicDetailsForm"
            await self.page.wait_for_selector(form_selector, timeout=15000)
            
            # Important: Wait for async dropdown values / spinners to disappear/resolve
            await self.page.wait_for_timeout(5000)
            
            # 4. Helper function to select custom Naukri dropdowns
            async def select_custom_dropdown(trigger_selector: str, option_selector: str, label: str):
                logger.info(f"Selecting {label}...")
                await self.page.click(trigger_selector)
                await self.page.wait_for_timeout(500)  # Wait for animation
                await self.page.wait_for_selector(option_selector, state="visible", timeout=5000)
                await self.page.click(option_selector)
                await self.page.wait_for_timeout(500)
                
            # 5. Populate Year dropdown
            await select_custom_dropdown(
                trigger_selector="#lwdYearFor",
                option_selector=f'a[data-id="lwdYear_{year}"]',
                label="Year"
            )
            
            # 6. Populate Month dropdown
            await select_custom_dropdown(
                trigger_selector="#lwdMonthFor",
                option_selector=f'a[data-id="lwdMonth_{month_num}"]',
                label="Month"
            )
            
            # 7. Populate Day dropdown
            await select_custom_dropdown(
                trigger_selector="#lwdDayFor",
                option_selector=f'a[data-id="lwdDay_{day}"]',
                label="Day"
            )
            
            # 8. Click Save
            save_btn_selector = "#saveBasicDetailsBtn"
            logger.info("Clicking Save button...")
            await self.page.click(save_btn_selector)
            
            # 9. Wait for completion notification or drawer closing
            await self.page.wait_for_timeout(5000)
            
            logger.info("✅ Notice Period LWD updated successfully!")
            return True
            
        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout while interacting with profile LWD fields: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to update last working day: {e}")
            return False

    async def apply_to_recommended_jobs(self, max_jobs: int = 5, use_bulk_select: bool = True) -> dict:
        """
        Apply to recommended Naukri jobs.
        
        Args:
            max_jobs: Maximum number of jobs to apply to (default: 5)
            use_bulk_select: Whether to use new bulk select mode (Phase 2) or legacy per-job mode (default: True)
        
        Returns:
            Dictionary with application statistics
        """
        logger.info(f"Starting auto-apply process for up to {max_jobs} Naukri jobs...")
        logger.info(f"Mode: {'Bulk Select (Phase 2)' if use_bulk_select else 'Per-Job Legacy'}")
        logger.info("="*70)
        
        results = {
            'total_attempted': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'external_redirects': 0,
            'external_jobs': [],  # Track jobs that redirect to external sites
            'details': [],
            'selector_validation': None,
            'bulk_select_results': None
        }
        
        try:
            # First, check if profile update was already done today
            project_root = Path(__file__).resolve().parents[2]
            update_track_file = project_root / "personal_details" / "last_profile_update.json"
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            should_update = True
            if update_track_file.exists():
                try:
                    with open(update_track_file, 'r', encoding='utf-8') as f:
                        track_data = json.load(f)
                        if track_data.get("last_naukri_lwd_update") == today_str:
                            should_update = False
                            logger.info("ℹ️ Profile last working day already updated today. Skipping step.")
                except Exception as e:
                    logger.warning(f"Could not read profile update tracking file: {e}")
                    
            if should_update:
                logger.info("Step 0: Updating profile last working day (current date + 60 days)...")
                lwd_success = await self.update_last_working_day(days_offset=60)
                if not lwd_success:
                    logger.warning("⚠️ Failed to update profile last working day. Proceeding with application flow anyway.")
                else:
                    logger.info("✅ Profile last working day updated successfully.")
                    try:
                        update_track_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(update_track_file, 'w', encoding='utf-8') as f:
                            json.dump({"last_naukri_lwd_update": today_str}, f)
                    except Exception as e:
                        logger.warning(f"Could not write profile update tracking file: {e}")
            else:
                lwd_success = True

            # Navigate to recommended jobs page
            logger.info(f"Navigating to: {self.RECOMMENDED_JOBS_URL}")
            await self.page.goto(self.RECOMMENDED_JOBS_URL, wait_until='domcontentloaded', timeout=60000)
            logger.info("Page loaded. Waiting for job cards to be visible...")
            await self.page.wait_for_selector(self.SELECTORS['job_cards'], timeout=30000)
            
            # Validate selectors on recommended jobs page
            if self.selector_validator:
                logger.info("\n🔍 Validating selectors on recommended jobs page...")
                await self.selector_validator.validate_all_selectors()
                self.selector_validator.print_summary()
                self.selector_validation_report = self.selector_validator.export_report()
                results['selector_validation'] = self.selector_validation_report
                logger.info(f"✅ Selector validation report saved: {self.selector_validation_report}\n")
            
            # Get all job cards
            logger.info("Fetching job listings...")
            job_cards = await self.page.query_selector_all(self.SELECTORS['job_cards'])
            logger.info(f"Found {len(job_cards)} job cards on the page")
            
            if not job_cards:
                logger.warning("No job cards found on the page.")
                return results

            if use_bulk_select:
                # Phase 2: Bulk select mode
                logger.info("\n" + "="*70)
                logger.info("🔄 PHASE 2: Bulk Select Mode")
                logger.info("="*70)
            
                # Step 1: Select multiple jobs
                selected_jobs = await self.select_jobs_bulk(max_jobs=max_jobs)
                results['bulk_select_results'] = selected_jobs
                
                if not selected_jobs:
                    logger.warning("⚠️  No jobs selected. Falling back to legacy per-job mode.")
                    use_bulk_select = False
                else:
                    jobs_selected = len(selected_jobs)
                    logger.info(f"\n✅ Selected {jobs_selected} jobs successfully")
                    
                    # Step 2: Click bulk apply button
                    apply_result = await self.click_bulk_apply_button()
                    
                    if apply_result['success']:
                        logger.info("✅ Bulk apply clicked. Side panel chatbot should appear.")

                        form_filler = NaukriFormFiller(
                            self.page,
                            self.vector_db,
                            confidence_threshold=0.60,
                            enable_logging=True,
                            enable_selector_validation=False
                        )

                        panel_appeared = await form_filler.wait_for_side_panel_chatbot(timeout_ms=25000)

                        if not panel_appeared:
                            logger.warning("⚠️  Chatbot side panel did not appear after Apply")
                            results['failed'] = jobs_selected
                            results['total_attempted'] = jobs_selected
                            current_time = datetime.now().isoformat()
                            for job in selected_jobs:
                                results['details'].append({
                                    'job_title': job['job_title'],
                                    'company_name': job['company_name'],
                                    'job_url': job['job_url'],
                                    'timestamp': current_time,
                                    'status': 'failed',
                                    'message': 'Chatbot side panel did not appear'
                                })
                        else:
                            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                            review_log = str(Path('logs') / f'naukri_chatbot_review_{ts}.json')

                            conv = await form_filler.run_chatbot_conversation(
                                allow_human_input=self.enable_human_fallback,
                                review_log_path=review_log,
                            )
                            results['chatbot_stats'] = conv
                            results['total_attempted'] = jobs_selected

                            # Verify application success using new helper
                            verification = await form_filler.verify_chatbot_application_success()
                            
                            if verification['success']:
                                results['successful'] = jobs_selected
                                results['failed'] = 0
                                status = 'successful'
                                message = f"Successfully applied. Verification: {verification['message']}"
                                self.jobs_applied += jobs_selected
                            else:
                                results['successful'] = 0
                                results['failed'] = jobs_selected
                                status = 'failed'
                                message = f"Application verification failed. Verification: {verification['message']}"
                                self.jobs_failed += jobs_selected

                            current_time = datetime.now().isoformat()
                            for job in selected_jobs:
                                results['details'].append({
                                    'job_title': job['job_title'],
                                    'company_name': job['company_name'],
                                    'job_url': job['job_url'],
                                    'timestamp': current_time,
                                    'status': status,
                                    'message': message
                                })
                            logger.info(
                                f"✅ Chatbot batch done: success={verification['success']}, "
                                f"answered={conv['answered']}, review={len(conv['review'])}"
                            )
                    else:
                        logger.error(f"❌ Failed to click bulk apply button: {apply_result['errors']}")
                        results['failed'] = jobs_selected
                        results['total_attempted'] = jobs_selected
                        current_time = datetime.now().isoformat()
                        for job in selected_jobs:
                            results['details'].append({
                                    'job_title': job['job_title'],
                                    'company_name': job['company_name'],
                                    'job_url': job['job_url'],
                                    'timestamp': current_time,
                                    'status': 'failed',
                                    'message': f"Failed to click bulk apply button: {', '.join(apply_result['errors'])}"
                            })
            
            # Legacy mode: Per-job application
            if not use_bulk_select:
                logger.info("\n" + "="*70)
                logger.info("📋 Legacy Mode: Per-Job Application")
                logger.info("="*70)
                
                # Limit to max_jobs
                jobs_to_apply = min(len(job_cards), max_jobs)
                logger.info(f"Will attempt to apply to {jobs_to_apply} jobs")
                
                # Process each job individually (original logic)
                for idx, job_card in enumerate(job_cards[:jobs_to_apply], 1):
                    try:
                        # Close any popups that might be blocking
                        await self._close_popups()
                        
                        # Try to scroll the job card into view
                        await job_card.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)
                        
                        # Extract job information
                        job_title = await self._extract_text(job_card, self.SELECTORS['job_card_title'])
                        
                        company_name = "Unknown Company"
                        company_elem = await job_card.query_selector('.companyName, [data-qa="companyName"], [data-qa="jobCardCompanyName"], [class*="company"]')
                        if company_elem:
                            company_name = (await company_elem.inner_text()).strip()
                            
                        # Extract job URL from card
                        job_url = ""
                        url_elem = await job_card.query_selector('a[href*="/jobs/"], a.title, a[data-qa="jobCardCurrentJobTitle"], a')
                        if url_elem:
                            href = await url_elem.get_attribute('href')
                            if href:
                                if href.startswith('/'):
                                    job_url = f"https://www.naukri.com{href}"
                                else:
                                    job_url = href
                                    
                        logger.info(f"\n[{idx}/{jobs_to_apply}] Processing job: {job_title} at {company_name}")
                        
                        # Log selector usage
                        if self.selector_validator:
                            await self.selector_validator.log_selector_usage(
                                'job_card_title', 
                                self.SELECTORS['job_card_title']
                            )
                        
                        # Click on the job card to load details
                        async with self.page.context.expect_page() as new_page_info:
                            await job_card.click()
                        
                        new_page = await new_page_info.value
                        await new_page.wait_for_load_state('domcontentloaded')
                        
                        # Get job URL to pass to form filler
                        final_job_url = new_page.url or job_url
                        logger.debug(f"Job URL: {final_job_url}")
                        
                        # Check if job redirected to external site
                        if "naukri.com" not in new_page.url:
                            logger.warning(f"⚠️  Job redirects to external site: {new_page.url}")
                            results['external_redirects'] += 1
                            results['skipped'] += 1
                            results['external_jobs'].append({
                                'job_title': job_title,
                                'redirect_url': new_page.url,
                                'timestamp': datetime.now().isoformat()
                            })
                            results['details'].append({
                                'job_title': job_title,
                                'company_name': company_name,
                                'job_url': final_job_url,
                                'timestamp': datetime.now().isoformat(),
                                'status': 'skipped',
                                'message': f'External redirect: {new_page.url}'
                            })
                            results['total_attempted'] += 1
                            continue
                        
                        # Try to find apply button with retry logic
                        apply_button = None
                        
                        try:
                            # Wait up to 15 seconds for Javascript to render the button on the new tab
                            apply_button = await new_page.wait_for_selector(self.SELECTORS['apply_button'], timeout=15000)
                        except Exception as e:
                            logger.debug(f"Apply button did not render within timeout: {e}")
                        
                        # Log selector usage
                        if self.selector_validator:
                            await self.selector_validator.log_selector_usage(
                                'apply_button', 
                                self.SELECTORS['apply_button']
                            )
                        
                        if apply_button:
                            # Check if button is enabled and visible
                            is_visible = await apply_button.is_visible()
                            is_enabled = await apply_button.is_enabled()
                            
                            logger.info(f"Apply button state: Visible={is_visible}, Enabled={is_enabled}")
                            
                            if not is_visible:
                                logger.debug("Scrolling apply button into view...")
                                await apply_button.scroll_into_view_if_needed()
                                await asyncio.sleep(1)
                            
                            if is_enabled:
                                try:
                                    logger.info("Clicking apply button...")
                                    await apply_button.click()
                                    await asyncio.sleep(3)  # Wait for form to appear (increased from 2)
                                    
                                    # Initialize form filler
                                    form_filler = NaukriFormFiller(
                                        new_page,
                                        self.vector_db,
                                        confidence_threshold=0.70,
                                        enable_logging=False,
                                        enable_selector_validation=False
                                    )
                                    
                                    try:
                                        # Fill the form automatically
                                        logger.info("Auto-filling form with semantic matching...")
                                        session = await form_filler.fill_naukri_job_application(
                                            job_url=new_page.url,
                                            max_questions=None,
                                            dry_run=False,
                                            allow_human_input=self.enable_human_fallback,  # Allow human intervention
                                            submit_form=True,  # Auto-submit
                                            navigate=False  # We are already on the page and have clicked apply
                                        )
                                        
                                        if session.status == "completed":
                                            logger.info(f"✅ Successfully applied to: {job_title}")
                                            results['successful'] += 1
                                            results['details'].append({
                                                'job_title': job_title,
                                                'company_name': company_name,
                                                'job_url': final_job_url,
                                                'timestamp': datetime.now().isoformat(),
                                                'status': 'successful',
                                                'message': 'Form filled and submitted'
                                            })
                                            self.jobs_applied += 1
                                        elif session.status == "partial":
                                            logger.info(f"⚠️ Partially filled form for: {job_title}")
                                            results['successful'] += 1
                                            results['details'].append({
                                                'job_title': job_title,
                                                'company_name': company_name,
                                                'job_url': final_job_url,
                                                'timestamp': datetime.now().isoformat(),
                                                'status': 'successful',
                                                'message': 'Some fields were filled'
                                            })
                                            self.jobs_applied += 1
                                        else:
                                            logger.warning(f"❌ Failed to apply to: {job_title} - {session.error_message}")
                                            results['failed'] += 1
                                            results['details'].append({
                                                'job_title': job_title,
                                                'company_name': company_name,
                                                'job_url': final_job_url,
                                                'timestamp': datetime.now().isoformat(),
                                                'status': 'failed',
                                                'message': session.error_message or 'Unknown error'
                                            })
                                            self.jobs_failed += 1
                                    
                                    except Exception as e:
                                        logger.error(f"Error filling form for {job_title}: {str(e)}")
                                        results['failed'] += 1
                                        results['details'].append({
                                            'job_title': job_title,
                                            'company_name': company_name,
                                            'job_url': final_job_url,
                                            'timestamp': datetime.now().isoformat(),
                                            'status': 'failed',
                                            'message': f'Form filling error: {str(e)}'
                                        })
                                        self.jobs_failed += 1
                                
                                except Exception as e:
                                    logger.error(f"Error clicking apply button for {job_title}: {str(e)}")
                                    results['failed'] += 1
                                    results['details'].append({
                                        'job_title': job_title,
                                        'company_name': company_name,
                                        'job_url': final_job_url,
                                        'timestamp': datetime.now().isoformat(),
                                        'status': 'failed',
                                        'message': f'Apply button click error: {str(e)}'
                                    })
                                    self.jobs_failed += 1
                            else:
                                logger.warning(f"⚠️  Apply button is disabled for: {job_title}")
                                results['skipped'] += 1
                                results['details'].append({
                                    'job_title': job_title,
                                    'company_name': company_name,
                                    'job_url': final_job_url,
                                    'timestamp': datetime.now().isoformat(),
                                    'status': 'skipped',
                                    'message': 'Apply button is disabled'
                                })
                        else:
                            logger.warning(f"❌ Apply button not found for: {job_title}")
                            results['skipped'] += 1
                            results['details'].append({
                                'job_title': job_title,
                                'company_name': company_name,
                                'job_url': final_job_url,
                                'timestamp': datetime.now().isoformat(),
                                'status': 'skipped',
                                'message': 'Apply button not available'
                            })
                        
                        results['total_attempted'] += 1
                    
                    except Exception as e:
                        logger.error(f"Error processing job {idx}: {str(e)}")
                        results['failed'] += 1
                        results['total_attempted'] += 1
                        results['details'].append({
                            'job_title': job_title if 'job_title' in locals() else f'Job {idx}',
                            'company_name': company_name if 'company_name' in locals() else 'Unknown Company',
                            'job_url': final_job_url if 'final_job_url' in locals() else (job_url if 'job_url' in locals() else ''),
                            'timestamp': datetime.now().isoformat(),
                            'status': 'failed',
                            'message': str(e)
                        })
                        self.jobs_failed += 1
            
            # Print summary
            logger.info("\n" + "="*60)
            logger.info("📊 AUTO-APPLY SUMMARY")
            logger.info("="*60)
            logger.info(f"Total Attempted: {results['total_attempted']}")
            logger.info(f"Successful: {results['successful']}")
            logger.info(f"Failed: {results['failed']}")
            logger.info(f"Skipped: {results['skipped']}")
            logger.info(f"External Redirects: {results['external_redirects']}")
            
            # Log external jobs to file if any
            if results['external_jobs']:
                self.log_external_jobs(results['external_jobs'])
            
            # Print diagnostics
            if self.selector_validator:
                logger.info(f"\n🔍 DIAGNOSTICS")
                logger.info(f"   Selector validations performed: {len(self.selector_validator.usage_log)}")
                if self.selector_validation_report:
                    logger.info(f"   Validation report: {self.selector_validation_report}")
            
            logger.info("="*60)
        
        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in auto-apply: {str(e)}")
        
        # Save dashboard report before returning results
        try:
            from scripts.common_stuff.application_dashboard import ApplicationDashboardWriter
            dashboard_writer = ApplicationDashboardWriter()
            summary = {
                'attempted': results.get('total_attempted', 0),
                'successful': results.get('successful', 0),
                'failed': results.get('failed', 0),
                'skipped': results.get('skipped', 0)
            }
            dashboard_writer.write_run(
                portal_name='Naukri',
                summary=summary,
                applications=results.get('details', [])
            )
            logger.info("✅ Dashboard report written successfully to JSON and CSV.")
        except Exception as e:
            logger.error(f"Failed to write dashboard report: {e}")

        return results
    
    async def _close_popups(self) -> None:
        """Close any popups that might block interaction."""
        try:
            popup = await self.page.query_selector(self.SELECTORS['popup_close'])
            if popup and await popup.is_visible():
                await popup.click()
                await asyncio.sleep(0.5)
        except:
            pass
    
    async def _extract_text(self, element, selector: str) -> str:
        """Extract text from an element using selector."""
        try:
            sub_elem = await element.query_selector(selector)
            if sub_elem:
                return await sub_elem.text_content()
        except:
            pass
        return "Unknown Job"
    
    def get_statistics(self) -> dict:
        """Get application statistics."""
        return {
            'jobs_applied': self.jobs_applied,
            'jobs_failed': self.jobs_failed,
            'total': self.jobs_applied + self.jobs_failed
        }
    
    def get_diagnostics(self) -> dict:
        """Get diagnostic information from selector validation."""
        diagnostics = {
            'selector_validation_enabled': self.selector_validator is not None,
            'selector_validation_report': self.selector_validation_report,
            'selector_usage_log_entries': len(self.selector_validator.usage_log) if self.selector_validator else 0,
            'timestamp': datetime.now().isoformat()
        }
        return diagnostics
    
    def log_external_jobs(self, external_jobs: List[Dict], output_dir: str = 'logs') -> str:
        """
        Log external job redirects to a JSON file for later review.
        
        Args:
            external_jobs: List of dicts with job_title, redirect_url, timestamp
            output_dir: Directory to save the log file
        
        Returns:
            Path to saved log file
        """
        try:
            from pathlib import Path
            
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True, parents=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = output_path / f"external_job_redirects_{timestamp}.json"
            
            with open(log_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'count': len(external_jobs),
                    'external_jobs': external_jobs
                }, f, indent=2)
            
            logger.info(f"📁 External jobs logged to: {log_file}")
            return str(log_file)
        except Exception as e:
            logger.error(f"Error logging external jobs: {e}")
            return None
    
    def export_diagnostics(self, filepath: str = None) -> str:
        """Export diagnostic logs to JSON file."""
        if not self.selector_validator:
            logger.warning("Selector validation not enabled - no diagnostics to export")
            return None
        
        return self.selector_validator.export_report(filepath)


async def main():
    """Example usage."""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state="naukri_cookies.json")
        page = await context.new_page()
        
        vector_db = VectorDBManager()
        applier = NaukriJobApply(page, vector_db)
        
        results = await applier.apply_to_recommended_jobs(max_jobs=5)
        print("\n📋 Results:")
        print(f"Successful: {results['successful']}")
        print(f"Failed: {results['failed']}")
        print(f"Skipped: {results['skipped']}")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
