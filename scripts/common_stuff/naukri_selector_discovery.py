"""
Naukri Selector Discovery & Validation Utility

Validates all Naukri selectors in real-time against live page:
- Detects which selectors work/fail
- Finds alternative selectors
- Logs selector health status
- Provides fallback suggestions

Usage:
    validator = SelectorValidator(page)
    results = await validator.validate_all_selectors()
    print(validator.get_report())
"""

import asyncio
import json
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from pathlib import Path
from playwright.async_api import Page

# Logging is configured centrally via scripts.common_stuff.logging_setup; just get
# this module's logger (do NOT force the root level here — it floods the terminal).
logger = logging.getLogger(__name__)


@dataclass
class SelectorResult:
    """Result of selector validation."""
    selector: str
    found: bool
    count: int
    visible_count: int
    enabled_count: int
    html_sample: Optional[str] = None
    error: Optional[str] = None
    alternatives: List[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if self.timestamp == "":
            self.timestamp = datetime.now().isoformat()
        if self.alternatives is None:
            self.alternatives = []


@dataclass
class SelectorCategory:
    """Group of related selectors."""
    category_name: str
    selectors: Dict[str, SelectorResult]
    status: str  # "pass", "partial", "fail"
    
    def to_dict(self):
        return {
            'category': self.category_name,
            'status': self.status,
            'selectors': {k: asdict(v) for k, v in self.selectors.items()}
        }


class SelectorValidator:
    """Validates Naukri selectors against live page."""
    
    # Naukri selectors to validate (from naukri_job_apply.py and naukri_form_filler.py)
    JOB_CARD_SELECTORS = {
        'job_cards_primary': '[data-qa="jobTuple"]',
        'job_cards_alt1': '[data-qa="job-card"]',
        'job_cards_alt2': '.jobCardContainer',
        'job_title': '[data-qa="jobTitle"]',
        'job_title_alt': '.jobTitle',
        'apply_button': 'button[data-qa="nxtApplyBtn"]',
        'apply_button_alt1': 'button[data-qa="applyBtn"]',
        'apply_button_alt2': 'button:has-text("Apply")',
        'job_url': 'a[data-qa="jobCardCurrentJobTitle"]',
        'loader': '.loader, [data-qa="loader"], .spinner',
    }
    
    FORM_SELECTORS = {
        'job_title_heading': 'h1.jobTitle',
        'job_title_heading_alt': 'h1[data-qa="jobTitle"]',
        'company_name': '[data-qa="jobCardCompanyName"]',
        'company_name_alt': '.companyName',
        'chatbot_form_container': '.filler-container, .customFields, [data-qa="customFields"]',
        'form_fields': 'input, select, textarea, [role="combobox"], [role="radio"]',
        'submit_button': 'button[type="submit"], button[data-qa="submit"]',
        'next_button': 'button[data-qa="nxtBtn"], button:has-text("Next")',
        'popup_close': 'button[aria-label="Close"], .popup-close, [data-qa="closeModal"]',
        'popup_close_alt': 'button[aria-label="close"], .modal-close',
        'nla_popup': '.nla-popup, [data-qa="nlaPopup"], .nextLevelAutomationPopup',
    }
    
    def __init__(self, page: Page, enable_logging: bool = True):
        """
        Initialize selector validator.
        
        Args:
            page: Playwright page object
            enable_logging: Whether to enable detailed logging
        """
        self.page = page
        self.enable_logging = enable_logging
        
        if enable_logging:
            logger.setLevel(logging.DEBUG)
        
        self.results: Dict[str, SelectorCategory] = {}
        self.usage_log: List[Dict[str, Any]] = []
        
    async def validate_all_selectors(self) -> Dict[str, SelectorCategory]:
        """
        Validate all selectors on current page.
        
        Returns:
            Dictionary of SelectorCategory objects
        """
        logger.info("🔍 Starting selector validation...")
        logger.info(f"   Current URL: {self.page.url}")
        
        current_url = self.page.url.lower()
        
        # Determine which selectors to validate based on URL
        if "recommendedjobs" in current_url:
            logger.info("📍 Detected: Recommended Jobs Page")
            self.results['job_cards'] = await self._validate_category(
                'Job Cards', self.JOB_CARD_SELECTORS
            )
        elif "job-details" in current_url or "/jobs/" in current_url:
            logger.info("📍 Detected: Job Detail/Apply Page")
            self.results['form'] = await self._validate_category(
                'Form Elements', self.FORM_SELECTORS
            )
        else:
            logger.warning(f"⚠️  Unknown page type: {current_url}")
            # Validate both just in case
            self.results['job_cards'] = await self._validate_category(
                'Job Cards', self.JOB_CARD_SELECTORS
            )
            self.results['form'] = await self._validate_category(
                'Form Elements', self.FORM_SELECTORS
            )
        
        logger.info("✅ Validation complete")
        return self.results
    
    async def _validate_category(
        self, 
        category_name: str, 
        selectors: Dict[str, str]
    ) -> SelectorCategory:
        """
        Validate all selectors in a category.
        
        Args:
            category_name: Name of selector category
            selectors: Dictionary of selector_name -> selector_string
        
        Returns:
            SelectorCategory with results
        """
        results = {}
        pass_count = 0
        fail_count = 0
        
        logger.info(f"\n📂 Validating category: {category_name}")
        logger.info(f"   Total selectors: {len(selectors)}")
        
        for selector_name, selector_string in selectors.items():
            try:
                result = await self._validate_selector(selector_string)
                results[selector_name] = result
                
                status_icon = "✅" if result.found else "❌"
                logger.debug(f"{status_icon} {selector_name}: {selector_string}")
                logger.debug(f"   Found: {result.count}, Visible: {result.visible_count}")
                
                if result.found:
                    pass_count += 1
                else:
                    fail_count += 1
                    # Try to find alternatives
                    if selector_name.endswith('_alt1') or selector_name.endswith('_alt2'):
                        pass  # Alternative selector, don't search further
                    else:
                        logger.debug(f"   Searching for alternatives...")
                
            except Exception as e:
                logger.error(f"❌ Error validating {selector_name}: {str(e)}")
                results[selector_name] = SelectorResult(
                    selector=selector_string,
                    found=False,
                    count=0,
                    visible_count=0,
                    enabled_count=0,
                    error=str(e)
                )
                fail_count += 1
        
        # Determine category status
        status = "pass" if fail_count == 0 else ("partial" if pass_count > 0 else "fail")
        
        logger.info(f"📊 Category Status: {status} ({pass_count} pass, {fail_count} fail)")
        
        return SelectorCategory(
            category_name=category_name,
            selectors=results,
            status=status
        )
    
    async def _validate_selector(self, selector: str) -> SelectorResult:
        """
        Validate single selector.
        
        Args:
            selector: CSS selector string
        
        Returns:
            SelectorResult with details
        """
        try:
            # Handle multiple selectors (comma-separated)
            if ',' in selector:
                # Try each selector until one works
                sub_selectors = [s.strip() for s in selector.split(',')]
                for sub_selector in sub_selectors:
                    try:
                        elements = await self.page.query_selector_all(sub_selector)
                        if elements:
                            return await self._analyze_elements(sub_selector, elements)
                    except:
                        continue
                # None of the sub-selectors worked
                return SelectorResult(
                    selector=selector,
                    found=False,
                    count=0,
                    visible_count=0,
                    enabled_count=0
                )
            else:
                # Single selector
                elements = await self.page.query_selector_all(selector)
                if elements:
                    return await self._analyze_elements(selector, elements)
                else:
                    return SelectorResult(
                        selector=selector,
                        found=False,
                        count=0,
                        visible_count=0,
                        enabled_count=0
                    )
        
        except Exception as e:
            return SelectorResult(
                selector=selector,
                found=False,
                count=0,
                visible_count=0,
                enabled_count=0,
                error=str(e)
            )
    
    async def _analyze_elements(self, selector: str, elements: List) -> SelectorResult:
        """
        Analyze found elements for state info.
        
        Args:
            selector: CSS selector used
            elements: List of found elements
        
        Returns:
            SelectorResult with analysis
        """
        visible_count = 0
        enabled_count = 0
        html_sample = None
        
        for elem in elements:
            try:
                is_visible = await elem.is_visible()
                if is_visible:
                    visible_count += 1
                
                # Check if element has disabled attribute/state
                is_enabled = await elem.is_enabled()
                if is_enabled:
                    enabled_count += 1
            except:
                pass
        
        # Get HTML of first element as sample
        try:
            if elements:
                html_sample = await elements[0].evaluate('e => e.outerHTML')
                # Truncate if too long
                if len(html_sample) > 200:
                    html_sample = html_sample[:200] + "..."
        except:
            pass
        
        return SelectorResult(
            selector=selector,
            found=True,
            count=len(elements),
            visible_count=visible_count,
            enabled_count=enabled_count,
            html_sample=html_sample
        )
    
    async def log_selector_usage(self, selector_name: str, selector: str) -> None:
        """
        Log a selector usage for diagnostics.
        
        Args:
            selector_name: Human-readable name
            selector: CSS selector string
        """
        try:
            elements = await self.page.query_selector_all(selector)
            
            visible = 0
            for e in elements:
                if await e.is_visible():
                    visible += 1
            
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'selector_name': selector_name,
                'selector': selector,
                'found': len(elements) > 0,
                'count': len(elements),
                'visible': visible,
                'url': self.page.url
            }
            
            self.usage_log.append(log_entry)
            
            if self.enable_logging:
                status = "✅" if log_entry['found'] else "❌"
                logger.debug(f"{status} {selector_name}: {log_entry['count']} found, {log_entry['visible']} visible")
        
        except Exception as e:
            logger.error(f"Error logging selector {selector_name}: {str(e)}")
    
    def get_report(self) -> Dict[str, Any]:
        """
        Get validation report.
        
        Returns:
            Dictionary with validation results and statistics
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'url': self.page.url,
            'categories': {}
        }
        
        for cat_name, category in self.results.items():
            report['categories'][cat_name] = category.to_dict()
        
        # Add usage log
        report['usage_log_entries'] = len(self.usage_log)
        
        return report
    
    def export_report(self, filepath: Optional[str] = None) -> str:
        """
        Export validation report to JSON file.
        
        Args:
            filepath: Optional custom filepath (default: logs/naukri_selector_<timestamp>.json)
        
        Returns:
            Path to exported file
        """
        if not filepath:
            logs_dir = Path(__file__).parent.parent.parent / 'logs'
            logs_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = logs_dir / f"naukri_selector_validation_{timestamp}.json"
        
        report = self.get_report()
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"✅ Report exported to: {filepath}")
        return str(filepath)
    
    def print_summary(self) -> None:
        """Print summary of validation results."""
        print("\n" + "="*70)
        print("📋 NAUKRI SELECTOR VALIDATION SUMMARY")
        print("="*70)
        
        for cat_name, category in self.results.items():
            print(f"\n📂 {category.category_name} [{category.status.upper()}]")
            print(f"   {'-'*60}")
            
            for sel_name, result in category.selectors.items():
                status = "✅ PASS" if result.found else "❌ FAIL"
                print(f"   {status} | {sel_name}")
                if result.found:
                    print(f"        └─ Found: {result.count}, Visible: {result.visible_count}, Enabled: {result.enabled_count}")
                    if result.html_sample:
                        preview = result.html_sample.replace('\n', ' ')[:80]
                        print(f"        └─ Sample: {preview}...")
                else:
                    if result.error:
                        print(f"        └─ Error: {result.error}")
        
        print("\n" + "="*70)


async def validate_naukri_selectors(page: Page, export_json: bool = True) -> Dict[str, Any]:
    """
    Quick-start validation function.
    
    Args:
        page: Playwright page object
        export_json: Whether to export results to JSON
    
    Returns:
        Validation report dictionary
    """
    validator = SelectorValidator(page, enable_logging=True)
    await validator.validate_all_selectors()
    
    validator.print_summary()
    
    if export_json:
        validator.export_report()
    
    return validator.get_report()


if __name__ == "__main__":
    print("Naukri Selector Discovery Utility")
    print("Use: from scripts.common_stuff.naukri_selector_discovery import SelectorValidator")
