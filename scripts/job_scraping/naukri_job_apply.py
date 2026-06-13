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
from datetime import datetime

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
    
    async def select_jobs_bulk(self, max_jobs: int = 5) -> dict:
        """
        Select multiple jobs at once before bulk apply (Phase 2).
        
        Args:
            max_jobs: Maximum number of jobs to select (default: 5)
        
        Returns:
            Dictionary with selection results
        """
        result = {
            'jobs_selected': 0,
            'selected_titles': [],
            'selection_method': None,
            'errors': []
        }
        
        try:
            logger.info(f"\n🔄 Starting bulk job selection (max {max_jobs})...")
            
            # Get all job cards
            job_cards = await self.page.query_selector_all(self.SELECTORS['job_cards'])
            logger.info(f"Found {len(job_cards)} total job cards")
            
            if not job_cards:
                logger.warning("No job cards found on the page")
                return result
            
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
                return result
            
            result['selection_method'] = selection_method
            
            # Select jobs one by one
            for idx, job_card in enumerate(job_cards[:jobs_to_select], 1):
                try:
                    await job_card.scroll_into_view_if_needed()
                    await asyncio.sleep(0.3)
                    
                    # Extract job title
                    job_title = await self._extract_text(job_card, self.SELECTORS['job_card_title'])
                    logger.info(f"  [{idx}/{jobs_to_select}] Selecting: {job_title}")
                    
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
                        
                        # Verify selection (check if checkbox is now checked or element has selected class)
                        if selection_method == 'checkbox':
                            try:
                                is_checked = await selection_element.is_checked()
                                logger.info(f"      ✅ Selected (checked={is_checked})")
                            except Exception:
                                logger.info(f"      ✅ Selected (clicked)")
                        else:
                            logger.info(f"      ✅ Selected")
                        
                        self.selected_job_cards.append(job_card)
                        self.selected_job_titles.append(job_title)
                        result['jobs_selected'] += 1
                        result['selected_titles'].append(job_title)
                        
                    else:
                        logger.warning(f"      ❌ Selection element not found for: {job_title}")
                        result['errors'].append(f"Selection element not found for job {idx}")
                
                except Exception as e:
                    logger.error(f"  Error selecting job {idx}: {str(e)}")
                    result['errors'].append(f"Job {idx}: {str(e)}")
            
            logger.info(f"\n✅ Selected {result['jobs_selected']} jobs for bulk apply")
            
        except Exception as e:
            logger.error(f"Error during bulk selection: {str(e)}")
            result['errors'].append(str(e))
        
        return result
    
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
                logger.warning("No job cards found on the page")
                return results
            
            if use_bulk_select:
                # Phase 2: Bulk select mode
                logger.info("\n" + "="*70)
                logger.info("🔄 PHASE 2: Bulk Select Mode")
                logger.info("="*70)
                
                # Step 1: Select multiple jobs
                select_result = await self.select_jobs_bulk(max_jobs=max_jobs)
                results['bulk_select_results'] = select_result
                
                if select_result['jobs_selected'] == 0:
                    logger.warning("⚠️  No jobs selected. Falling back to legacy per-job mode.")
                    use_bulk_select = False
                else:
                    jobs_selected = select_result['jobs_selected']
                    logger.info(f"\n✅ Selected {jobs_selected} jobs successfully")
                    
                    # Step 2: Click bulk apply button
                    apply_result = await self.click_bulk_apply_button()
                    
                    if apply_result['success']:
                        logger.info("✅ Bulk apply clicked. Side panel should appear for form filling.")
                        
                        # Step 3: Fill form for bulk-selected jobs
                        # The form will be for each selected job (depending on Naukri implementation)
                        logger.info("⏳ Waiting for side panel form to load...")
                        
                        form_filler = NaukriFormFiller(
                            self.page,
                            self.vector_db,
                            confidence_threshold=0.70,
                            enable_logging=True,
                            enable_selector_validation=False
                        )
                        
                        # For each selected job, fill the form
                        for job_idx, job_title in enumerate(select_result['selected_titles'], 1):
                            try:
                                logger.info(f"\n📋 [{job_idx}/{len(select_result['selected_titles'])}] Processing: {job_title}")
                                
                                # Wait for side panel form to appear
                                panel_appeared = await form_filler.wait_for_side_panel_chatbot(timeout_ms=25000)
                                
                                if not panel_appeared:
                                    logger.warning(f"⚠️  Side panel did not appear for {job_title}")
                                    results['skipped'] += 1
                                    results['details'].append({
                                        'job_title': job_title,
                                        'status': 'skipped',
                                        'message': 'Side panel did not appear'
                                    })
                                    results['total_attempted'] += 1
                                    continue
                                
                                # Detect questions in the side panel
                                questions = await form_filler.detect_chatbot_questions_in_panel()
                                
                                if not questions:
                                    logger.info(f"No questions detected in panel for {job_title}")
                                    # Still need to click Save to move to next job
                                    saved = await form_filler.click_chatbot_save_button()
                                    if saved:
                                        logger.info(f"✅ Moved to next job")
                                        results['successful'] += 1
                                    else:
                                        logger.warning(f"⚠️  Could not click Save button")
                                        results['skipped'] += 1
                                    results['total_attempted'] += 1
                                    continue
                                
                                logger.info(f"Found {len(questions)} questions to answer")
                                
                                # Fill the form using vector DB
                                fill_stats = await form_filler.fill_chatbot_form_for_job(
                                    job_title=job_title,
                                    questions=questions,
                                    allow_human_input=True  # Prompt user if confidence < 0.70
                                )
                                
                                # Click Save button to confirm this job and move to next
                                saved = await form_filler.click_chatbot_save_button()
                                
                                if saved:
                                    results['successful'] += 1
                                    logger.info(f"✅ Form completed and saved for {job_title}")
                                    results['details'].append({
                                        'job_title': job_title,
                                        'status': 'completed',
                                        'message': f'Answered {fill_stats["questions_answered"]}/{fill_stats["total_questions"]} questions',
                                        'stats': fill_stats
                                    })
                                else:
                                    results['failed'] += 1
                                    logger.warning(f"⚠️  Could not click Save button for {job_title}")
                                    results['details'].append({
                                        'job_title': job_title,
                                        'status': 'failed',
                                        'message': 'Could not click Save button',
                                        'stats': fill_stats
                                    })
                                
                                results['total_attempted'] += 1
                                
                            except Exception as e:
                                logger.error(f"Error processing {job_title}: {str(e)}")
                                results['failed'] += 1
                                results['total_attempted'] += 1
                                results['details'].append({
                                    'job_title': job_title,
                                    'status': 'failed',
                                    'message': f'Error: {str(e)}'
                                })
                    else:
                        logger.error(f"❌ Failed to click bulk apply button: {apply_result['errors']}")
                        results['failed'] = jobs_selected
                        results['total_attempted'] = jobs_selected
            
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
                        logger.info(f"\n[{idx}/{jobs_to_apply}] Processing job: {job_title}")
                        
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
                        job_url = new_page.url
                        logger.debug(f"Job URL: {job_url}")
                        
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
                                                'status': 'completed',
                                                'message': 'Form filled and submitted'
                                            })
                                            self.jobs_applied += 1
                                        elif session.status == "partial":
                                            logger.info(f"⚠️ Partially filled form for: {job_title}")
                                            results['successful'] += 1
                                            results['details'].append({
                                                'job_title': job_title,
                                                'status': 'partial',
                                                'message': 'Some fields were filled'
                                            })
                                            self.jobs_applied += 1
                                        else:
                                            logger.warning(f"❌ Failed to apply to: {job_title} - {session.error_message}")
                                            results['failed'] += 1
                                            results['details'].append({
                                                'job_title': job_title,
                                                'status': 'failed',
                                                'message': session.error_message or 'Unknown error'
                                            })
                                            self.jobs_failed += 1
                                    
                                    except Exception as e:
                                        logger.error(f"Error filling form for {job_title}: {str(e)}")
                                        results['failed'] += 1
                                        results['details'].append({
                                            'job_title': job_title,
                                            'status': 'failed',
                                            'message': f'Form filling error: {str(e)}'
                                        })
                                        self.jobs_failed += 1
                                
                                except Exception as e:
                                    logger.error(f"Error clicking apply button for {job_title}: {str(e)}")
                                    results['failed'] += 1
                                    results['details'].append({
                                        'job_title': job_title,
                                        'status': 'failed',
                                        'message': f'Apply button click error: {str(e)}'
                                    })
                                    self.jobs_failed += 1
                            else:
                                logger.warning(f"⚠️  Apply button is disabled for: {job_title}")
                                results['skipped'] += 1
                                results['details'].append({
                                    'job_title': job_title,
                                    'status': 'skipped',
                                    'message': 'Apply button is disabled'
                                })
                        else:
                            logger.warning(f"❌ Apply button not found for: {job_title}")
                            results['skipped'] += 1
                            results['details'].append({
                                'job_title': job_title,
                                'status': 'skipped',
                                'message': 'Apply button not available'
                            })
                        
                        results['total_attempted'] += 1
                    
                    except Exception as e:
                        logger.error(f"Error processing job {idx}: {str(e)}")
                        results['failed'] += 1
                        results['total_attempted'] += 1
                        results['details'].append({
                            'job_title': f'Job {idx}',
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
