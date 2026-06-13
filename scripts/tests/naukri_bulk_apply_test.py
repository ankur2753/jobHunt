#!/usr/bin/env python3
"""
Naukri Bulk Apply - Locator Discovery & Validation Test
Phase 1: MCP-assisted discovery of multi-select UI and side panel chatbot

Features:
  - Connect to browser via MCP server
  - Navigate to recommended jobs page
  - Discover job card selection UI (checkboxes, buttons)
  - Discover bulk apply button location (top right)
  - Discover side panel chatbot interface
  - Pause at key points for manual inspection
  - Generate diagnostic report with all discovered selectors

Usage:
    python scripts/tests/naukri_bulk_apply_test.py --max-jobs 5 --headed --pause
"""

import asyncio
import argparse
import sys
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from playwright.async_api import async_playwright, Page
from scripts.cookie_management_login.naukri_login import NaukriPlaywright
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.common_stuff.naukri_selector_discovery import SelectorValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NaukriBulkApplyTestRunner:
    """Test runner for Naukri bulk apply workflow with locator discovery."""
    
    def __init__(self, headless: bool = False, pause_at_stages: bool = False, verbose: bool = False):
        """
        Initialize test runner.
        
        Args:
            headless: Whether to run in headless mode
            pause_at_stages: Whether to pause at each stage for manual inspection
            verbose: Whether to enable verbose logging
        """
        self.headless = headless
        self.pause_at_stages = pause_at_stages
        self.verbose = verbose
        self.browser_manager = None
        self.page = None
        self.vector_db = None
        self.test_report = {
            'timestamp': datetime.now().isoformat(),
            'stages': {},
            'discovered_selectors': {},
            'results': {},
            'errors': []
        }
    
    async def setup(self) -> None:
        """Setup browser and dependencies."""
        logger.info("🔧 Setting up Naukri test environment...")
        
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
    
    async def run_test(self, max_jobs: int = 5) -> dict:
        """
        Run complete test with locator discovery.
        
        Args:
            max_jobs: Maximum jobs to test
        
        Returns:
            Test report dictionary
        """
        try:
            await self.setup()
            
            # Stage 1: Navigate and collect job cards
            stage_1_result = await self._stage_1_recommended_jobs_page()
            self.test_report['stages']['stage_1'] = stage_1_result
            
            if not stage_1_result['success']:
                logger.error("❌ Stage 1 failed - cannot proceed")
                return self.test_report
            
            await self._pause_if_requested("Stage 1: Recommended jobs page loaded. Inspect job card structure.")
            
            # Stage 2: Discover selection UI (checkboxes/buttons)
            stage_2_result = await self._stage_2_discover_selection_ui(
                max_jobs=min(max_jobs, stage_1_result['job_cards_found'])
            )
            self.test_report['stages']['stage_2'] = stage_2_result
            self.test_report['discovered_selectors']['job_selection'] = stage_2_result['discovered_selectors']
            
            await self._pause_if_requested("Stage 2: Job selection UI discovered. Verify selection checkboxes.")
            
            # Stage 3: Simulate bulk selection and discover apply button
            stage_3_result = await self._stage_3_discover_bulk_apply_button(max_jobs)
            self.test_report['stages']['stage_3'] = stage_3_result
            self.test_report['discovered_selectors']['bulk_apply'] = stage_3_result['discovered_selectors']
            
            await self._pause_if_requested("Stage 3: Bulk apply button discovered. Verify button location (top right).")
            
            # Stage 4: Click apply and discover side panel chatbot
            stage_4_result = await self._stage_4_discover_side_panel_chatbot()
            self.test_report['stages']['stage_4'] = stage_4_result
            self.test_report['discovered_selectors']['side_panel'] = stage_4_result['discovered_selectors']
            
            await self._pause_if_requested("Stage 4: Side panel chatbot appeared. Inspect form structure and controls.")
            
            # Stage 5: Discover form elements in side panel
            stage_5_result = await self._stage_5_discover_form_elements()
            self.test_report['stages']['stage_5'] = stage_5_result
            self.test_report['discovered_selectors']['form_elements'] = stage_5_result['discovered_selectors']
            
            await self._pause_if_requested("Stage 5: Form elements discovered. Inspect question area and answer controls.")
            
            # Summary
            self._print_report()
            
            return self.test_report
        
        except Exception as e:
            logger.error(f"❌ Test failed: {str(e)}", exc_info=True)
            self.test_report['error'] = str(e)
            return self.test_report
        
        finally:
            await self.cleanup()
    
    async def _pause_if_requested(self, message: str) -> None:
        """Pause execution if pause_at_stages flag is set."""
        if self.pause_at_stages:
            logger.info(f"\n⏸️  {message}")
            logger.info("Press Enter to continue...")
            await asyncio.get_event_loop().run_in_executor(None, input)
    
    async def _stage_1_recommended_jobs_page(self) -> dict:
        """
        Stage 1: Navigate to recommended jobs page and collect initial data.
        
        Returns:
            Stage result dictionary
        """
        logger.info("\n" + "="*70)
        logger.info("📋 STAGE 1: Navigate to Recommended Jobs Page")
        logger.info("="*70)
        
        result = {
            'success': False,
            'job_cards_found': 0,
            'url': None,
            'page_title': None,
            'errors': []
        }
        
        try:
            # Navigate to recommended jobs
            url = "https://www.naukri.com/mnjuser/recommendedjobs"
            logger.info(f"📍 Navigating to: {url}")
            await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(2)
            
            result['url'] = self.page.url
            result['page_title'] = await self.page.title()
            logger.info(f"✅ Page loaded: {result['page_title']}")
            
            # Wait for job cards
            logger.info("⏳ Waiting for job cards to load...")
            await self.page.wait_for_selector('.jobTuple', timeout=30000)
            
            # Collect job cards
            logger.info("📇 Collecting job cards...")
            job_cards = await self.page.query_selector_all('.jobTuple')
            
            result['job_cards_found'] = len(job_cards)
            logger.info(f"✅ Found {len(job_cards)} job cards")
            
            result['success'] = True
            
        except Exception as e:
            logger.error(f"❌ Stage 1 failed: {str(e)}")
            result['errors'].append(str(e))
        
        return result
    
    async def _stage_2_discover_selection_ui(self, max_jobs: int = 5) -> dict:
        """
        Stage 2: Discover job card selection UI (checkboxes or buttons).
        
        Args:
            max_jobs: Maximum jobs to inspect
        
        Returns:
            Stage result dictionary with discovered selectors
        """
        logger.info("\n" + "="*70)
        logger.info(f"📋 STAGE 2: Discover Job Selection UI (Testing {max_jobs} cards)")
        logger.info("="*70)
        
        result = {
            'jobs_inspected': 0,
            'discovered_selectors': {},
            'selection_methods': {},
            'errors': []
        }
        
        try:
            job_cards = await self.page.query_selector_all('.jobTuple')
            jobs_to_inspect = min(max_jobs, len(job_cards))
            
            logger.info(f"📇 Inspecting {jobs_to_inspect} job cards for selection UI...")
            
            for idx, job_card in enumerate(job_cards[:jobs_to_inspect], 1):
                try:
                    logger.info(f"\n  [{idx}/{jobs_to_inspect}] Analyzing job card structure...")
                    
                    # Try to find checkbox
                    checkbox = await job_card.query_selector('input[type="checkbox"]')
                    if checkbox:
                        is_visible = await checkbox.is_visible()
                        logger.info(f"    ✅ Found checkbox: visible={is_visible}")
                        result['discovered_selectors']['checkbox'] = 'input[type="checkbox"]'
                        result['selection_methods']['checkbox'] = 'click_checkbox'
                    
                    # Try to find selection button (data-qa or aria-label)
                    select_btn = await job_card.query_selector('button[data-qa*="select"], button[aria-label*="select"], button[title*="select"]')
                    if select_btn:
                        aria_label = await select_btn.get_attribute('aria-label')
                        logger.info(f"    ✅ Found select button: aria-label='{aria_label}'")
                        result['discovered_selectors']['select_button'] = 'button[data-qa*="select"]'
                        result['selection_methods']['select_button'] = 'click_button'
                    
                    # Try to find any clickable area with selection indicator
                    selection_area = await job_card.query_selector('[class*="select"], [data-qa*="select"]')
                    if selection_area and 'checkbox' not in result['discovered_selectors']:
                        logger.info(f"    ℹ️  Found selection-related element")
                    
                    result['jobs_inspected'] += 1
                    
                except Exception as e:
                    logger.error(f"    ❌ Error inspecting job {idx}: {str(e)}")
                    result['errors'].append({
                        'job_index': idx,
                        'error': str(e)
                    })
            
            # If no selection UI found, try hover/click behaviors
            if not result['discovered_selectors']:
                logger.warning("⚠️  No explicit selection UI found. Job cards may use hover or click-based selection.")
                result['discovered_selectors']['fallback'] = 'job_card_click_to_select'
                result['selection_methods']['fallback'] = 'click_job_card'
            
            logger.info(f"\n📊 Discovered selectors: {result['discovered_selectors']}")
            
        except Exception as e:
            logger.error(f"❌ Stage 2 failed: {str(e)}")
            result['errors'].append(str(e))
        
        return result
    
    async def _stage_3_discover_bulk_apply_button(self, max_jobs: int = 5) -> dict:
        """
        Stage 3: Discover bulk apply button location (top right corner).
        
        Args:
            max_jobs: Number of jobs to select
        
        Returns:
            Stage result dictionary with discovered button selector
        """
        logger.info("\n" + "="*70)
        logger.info(f"📋 STAGE 3: Discover Bulk Apply Button")
        logger.info("="*70)
        
        result = {
            'success': False,
            'discovered_selectors': {},
            'button_location': None,
            'errors': []
        }
        
        try:
            # Try common bulk action button selectors (usually top right)
            logger.info("🔍 Searching for bulk apply button...")
            
            potential_selectors = [
                'button[data-qa="applyBtn"], button[data-qa="nxtApplyBtn"]',
                'button:has-text("Apply")',
                'button[aria-label*="Apply"]',
                '.job-actions button[type="submit"]',
                'div[class*="action"] button[class*="apply"]',
                'button[class*="apply"][class*="bulk"]',
            ]
            
            found_button = None
            found_selector = None
            
            for selector in potential_selectors:
                try:
                    buttons = await self.page.query_selector_all(selector)
                    if buttons:
                        # Check if any are in top-right area (should be visible and near right edge)
                        for btn in buttons:
                            is_visible = await btn.is_visible()
                            if is_visible:
                                # Get bounding box to confirm it's in top-right
                                bbox = await btn.bounding_box()
                                if bbox:
                                    viewport_width = await self.page.evaluate('window.innerWidth')
                                    is_right_aligned = bbox['x'] > viewport_width * 0.7  # Right 30% of screen
                                    logger.info(f"✅ Found button with selector: {selector}")
                                    logger.info(f"   Position: x={bbox['x']}, y={bbox['y']}, width={bbox['width']}")
                                    logger.info(f"   Right-aligned: {is_right_aligned}")
                                    
                                    if is_right_aligned or found_button is None:
                                        found_button = btn
                                        found_selector = selector
                except:
                    continue
            
            if found_button:
                bbox = await found_button.bounding_box()
                result['discovered_selectors']['apply_button'] = found_selector
                result['button_location'] = {
                    'selector': found_selector,
                    'bounding_box': {
                        'x': bbox['x'],
                        'y': bbox['y'],
                        'width': bbox['width'],
                        'height': bbox['height']
                    }
                }
                result['success'] = True
                logger.info(f"📍 Bulk apply button located at: {result['button_location']}")
            else:
                logger.warning("⚠️  Could not locate bulk apply button in common locations")
                logger.info("    Hint: Check if button appears after selecting job cards")
                result['discovered_selectors']['apply_button'] = '[TBD - appears after selection]'
        
        except Exception as e:
            logger.error(f"❌ Stage 3 failed: {str(e)}")
            result['errors'].append(str(e))
        
        return result
    
    async def _stage_4_discover_side_panel_chatbot(self) -> dict:
        """
        Stage 4: Click apply button and discover side panel chatbot.
        
        Returns:
            Stage result dictionary with side panel selectors
        """
        logger.info("\n" + "="*70)
        logger.info("📋 STAGE 4: Discover Side Panel Chatbot")
        logger.info("="*70)
        
        result = {
            'success': False,
            'discovered_selectors': {},
            'panel_structure': {},
            'errors': []
        }
        
        try:
            # Try to find and click apply button
            logger.info("🔍 Looking for apply button to click...")
            
            apply_button = await self.page.query_selector('button[data-qa="nxtApplyBtn"], button[data-qa="applyBtn"], button:has-text("Apply")')
            
            if apply_button and await apply_button.is_visible():
                logger.info("👆 Clicking apply button...")
                await apply_button.click()
                await asyncio.sleep(3)  # Wait for panel to load
                
                logger.info("⏳ Waiting for side panel to appear...")
                
                # Try common side panel selectors
                panel_selectors = [
                    '.filler-container',
                    '.customFields',
                    '[data-qa="customFields"]',
                    '[role="form"]',
                    '.application-form',
                    '.chat-container',
                    '.chatbot',
                    '.chat-window',
                    '.nI-chat-container',
                    'aside',
                    '[class*="panel"]',
                    '[class*="sidebar"]',
                    '[class*="chat"]',
                ]
                
                found_panel = None
                found_selector = None
                
                for selector in panel_selectors:
                    try:
                        panels = await self.page.query_selector_all(selector)
                        if panels:
                            for panel in panels:
                                is_visible = await panel.is_visible()
                                if is_visible:
                                    # Check if it's on the right side
                                    bbox = await panel.bounding_box()
                                    if bbox:
                                        viewport_width = await self.page.evaluate('window.innerWidth')
                                        is_right_side = bbox['x'] > viewport_width * 0.5
                                        
                                        if is_right_side:
                                            logger.info(f"✅ Found side panel with selector: {selector}")
                                            found_panel = panel
                                            found_selector = selector
                                            break
                    except:
                        continue
                
                if found_panel:
                    bbox = await found_panel.bounding_box()
                    result['discovered_selectors']['panel_container'] = found_selector
                    result['panel_structure'] = {
                        'container_selector': found_selector,
                        'positioning': {
                            'x': bbox['x'],
                            'y': bbox['y'],
                            'width': bbox['width'],
                            'height': bbox['height'],
                            'is_right_side': bbox['x'] > await self.page.evaluate('window.innerWidth') * 0.5
                        }
                    }
                    result['success'] = True
                    logger.info(f"📍 Side panel structure: {result['panel_structure']}")
                else:
                    logger.warning("⚠️  Side panel not found. It may not be visible yet.")
            else:
                logger.warning("⚠️  Apply button not found or not visible")
                result['errors'].append('Apply button not found')
        
        except Exception as e:
            logger.error(f"❌ Stage 4 failed: {str(e)}")
            result['errors'].append(str(e))
        
        return result
    
    async def _stage_5_discover_form_elements(self) -> dict:
        """
        Stage 5: Discover form elements within side panel chatbot.
        
        Returns:
            Stage result dictionary with form element selectors
        """
        logger.info("\n" + "="*70)
        logger.info("📋 STAGE 5: Discover Side Panel Form Elements")
        logger.info("="*70)
        
        result = {
            'success': False,
            'discovered_selectors': {},
            'form_structure': {},
            'errors': []
        }
        
        try:
            logger.info("🔍 Scanning for form elements in side panel...")
            
            # Look for question display area
            question_selectors = [
                '.question',
                '[data-qa="question"]',
                '.chatbot-query',
                '.chat-message',
                '[class*="question"]',
                'p[class*="question"]',
                'div:has(+ input), div:has(+ select)',
            ]
            
            for selector in question_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        visible_count = 0
                        for elem in elements:
                            if await elem.is_visible():
                                visible_count += 1
                        if visible_count > 0:
                            logger.info(f"✅ Found question elements: {selector} ({visible_count} visible)")
                            result['discovered_selectors']['question_area'] = selector
                            break
                except:
                    continue
            
            # Look for answer input fields
            logger.info("\n🔍 Scanning for answer input fields...")
            
            answer_input_types = {
                'text_input': 'input[type="text"]',
                'number_input': 'input[type="number"]',
                'email_input': 'input[type="email"]',
                'textarea': 'textarea',
                'select': 'select',
                'radio': 'input[type="radio"]',
                'checkbox': 'input[type="checkbox"]',
            }
            
            for input_type, selector in answer_input_types.items():
                try:
                    inputs = await self.page.query_selector_all(selector)
                    if inputs:
                        visible_count = sum(1 for inp in inputs if asyncio.run(inp.is_visible()))
                        if visible_count > 0:
                            logger.info(f"✅ Found {input_type}: {selector} ({visible_count} visible)")
                            result['discovered_selectors'][f'{input_type}_field'] = selector
                except:
                    continue
            
            # Look for Save/Next button in side panel
            logger.info("\n🔍 Scanning for action buttons (Save/Next)...")
            
            action_button_selectors = [
                'button[data-qa="save"]',
                'button[data-qa="next"]',
                'button:has-text("Save")',
                'button:has-text("Next")',
                'button:has-text("Submit")',
                '.form-actions button',
                '[class*="action"] button',
            ]
            
            for selector in action_button_selectors:
                try:
                    buttons = await self.page.query_selector_all(selector)
                    if buttons:
                        visible_buttons = [btn for btn in buttons if asyncio.run(btn.is_visible())]
                        if visible_buttons:
                            logger.info(f"✅ Found action button: {selector}")
                            result['discovered_selectors']['action_button'] = selector
                            break
                except:
                    continue
            
            result['success'] = len(result['discovered_selectors']) > 0
            logger.info(f"\n📊 Discovered form elements: {result['discovered_selectors']}")
            
        except Exception as e:
            logger.error(f"❌ Stage 5 failed: {str(e)}")
            result['errors'].append(str(e))
        
        return result
    
    def _print_report(self) -> None:
        """Print summary report."""
        logger.info("\n" + "="*70)
        logger.info("📊 DISCOVERY TEST SUMMARY")
        logger.info("="*70)
        
        for stage, data in self.test_report['stages'].items():
            status = "✅ PASS" if data.get('success', data.get('job_cards_found', 0) > 0) else "❌ FAIL"
            logger.info(f"\n{stage}: {status}")
            if 'job_cards_found' in data:
                logger.info(f"  Job cards found: {data['job_cards_found']}")
            if 'jobs_inspected' in data:
                logger.info(f"  Jobs inspected: {data['jobs_inspected']}")
            if 'errors' in data and data['errors']:
                for error in data['errors']:
                    logger.warning(f"  Error: {error}")
        
        logger.info("\n" + "-"*70)
        logger.info("🔍 DISCOVERED SELECTORS")
        logger.info("-"*70)
        
        for section, selectors in self.test_report['discovered_selectors'].items():
            logger.info(f"\n{section.upper()}:")
            for key, value in selectors.items():
                logger.info(f"  {key}: {value}")
    
    async def cleanup(self) -> None:
        """Cleanup and close browser."""
        if self.browser_manager and self.browser_manager.browser:
            await self.browser_manager.browser.close()
            logger.info("✓ Browser closed")
        
        # Save report to file
        report_path = Path('logs') / f'naukri_bulk_apply_discovery_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(self.test_report, f, indent=2)
        
        logger.info(f"📁 Report saved to: {report_path}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Naukri Bulk Apply - Locator Discovery Test'
    )
    parser.add_argument(
        '--max-jobs',
        type=int,
        default=5,
        help='Maximum jobs to process (default: 5)'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run in headless mode (default: headed)'
    )
    parser.add_argument(
        '--headed',
        dest='headless',
        action='store_false',
        help='Run in headed mode with visible browser (default)'
    )
    parser.add_argument(
        '--pause',
        action='store_true',
        help='Pause at each stage for manual inspection'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    runner = NaukriBulkApplyTestRunner(
        headless=args.headless,  # If --headless is provided, it's true, else false.
        pause_at_stages=args.pause,
        verbose=args.verbose
    )
    
    report = await runner.run_test(max_jobs=args.max_jobs)
    
    # Return success/failure
    success = all(
        stage.get('success', stage.get('job_cards_found', 0) > 0)
        for stage in report['stages'].values()
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
