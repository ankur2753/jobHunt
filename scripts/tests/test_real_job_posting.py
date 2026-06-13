#!/usr/bin/env python3
"""
Test Script: Real Job Posting Form Filling Test
Phase 3: Validate form fillers with real Naukri/LinkedIn job postings

Usage:
    python test_real_job_posting.py --url "JOB_URL" --portal naukri --dry-run --headless

Features:
  - Test with real LinkedIn or Naukri job postings
  - Dry-run mode: Detect questions without filling
  - Manual mode: Auto-fill + human review
  - Full mode: Auto-fill + human fallback + submit
  - Headless or headed browser
  - Detailed logging and report generation
"""

import asyncio
import argparse
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from playwright.async_api import async_playwright
from scripts.cookie_management_login.linkedin_form_filler import LinkedInFormFiller
from scripts.cookie_management_login.naukri_form_filler import NaukriFormFiller
from scripts.cookie_management_login.naukri_login import NaukriPlaywright
from scripts.orchestrator.orchestrator import LinkedInPlaywright
from scripts.common_stuff.vector_db_manager import VectorDBManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealJobPostingTester:
    """Test form fillers with real job postings."""
    
    def __init__(self, portal: str = "naukri", headless: bool = True):
        """
        Initialize tester.
        
        Args:
            portal: "naukri" or "linkedin"
            headless: Whether to run in headless mode
        """
        self.portal = portal.lower()
        self.headless = headless
        self.browser_manager = None
        self.browser = None
        self.page = None
        self.vector_db = None
    
    async def setup(self) -> None:
        """Setup browser and vector DB."""
        logger.info(f"Setting up {self.portal.upper()} tester...")
        
        # Initialize vector DB
        self.vector_db = VectorDBManager()
        logger.info("✓ Vector DB initialized")
        
        # Setup browser manager based on portal
        if self.portal == "linkedin":
            self.browser_manager = LinkedInPlaywright()
        elif self.portal == "naukri":
            self.browser_manager = NaukriPlaywright()
        else:
            raise ValueError(f"Unknown portal: {self.portal}")
        
        # Setup browser
        await self.browser_manager.setup_driver(headless=self.headless)
        self.page = self.browser_manager.page
        logger.info("✓ Browser setup complete")
        
        # Check login
        if not await self.browser_manager.is_logged_in():
            logger.warning("⚠️ Not logged in")
            raise RuntimeError(f"Please log into {self.portal.upper()} first")
        
        logger.info(f"✓ Logged into {self.portal.upper()}")
    
    async def test_job_posting(
        self,
        job_url: str,
        dry_run: bool = True,
        auto_submit: bool = False
    ) -> dict:
        """
        Test form filling on a real job posting.
        
        Args:
            job_url: Job posting URL
            dry_run: If True, only detect without filling
            auto_submit: If True, submit form after filling (CAUTION!)
        
        Returns:
            Test results dictionary
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing {self.portal.upper()} Job Posting")
        logger.info(f"{'='*70}")
        logger.info(f"URL: {job_url}")
        logger.info(f"Mode: {'DRY-RUN' if dry_run else 'AUTO-FILL'}")
        if auto_submit:
            logger.warning(f"⚠️ AUTO-SUBMIT: Form will be submitted!")
        logger.info(f"{'='*70}\n")
        
        start_time = datetime.now()
        results = {
            'success': False,
            'portal': self.portal,
            'url': job_url,
            'start_time': start_time,
            'end_time': None,
            'duration_seconds': 0,
            'error': None,
            'report': None
        }
        
        try:
            # Create form filler based on portal
            if self.portal == "linkedin":
                form_filler = LinkedInFormFiller(
                    self.page,
                    self.vector_db,
                    confidence_threshold=0.65,
                    enable_logging=True
                )
                
                session = await form_filler.fill_linkedin_job_application(
                    job_url=job_url,
                    max_questions=None,
                    dry_run=dry_run,
                    allow_human_input=True,
                    submit_form=auto_submit
                )
            
            elif self.portal == "naukri":
                form_filler = NaukriFormFiller(
                    self.page,
                    self.vector_db,
                    confidence_threshold=0.70,
                    enable_logging=True
                )
                
                session = await form_filler.fill_naukri_job_application(
                    job_url=job_url,
                    max_questions=None,
                    dry_run=dry_run,
                    allow_human_input=True,
                    submit_form=auto_submit
                )
            
            # Get report
            report = form_filler.get_session_report()
            
            results['success'] = True
            results['report'] = report
            results['end_time'] = datetime.now()
            results['duration_seconds'] = (results['end_time'] - start_time).total_seconds()
            
            # Print report
            self._print_report(report)
        
        except asyncio.TimeoutError as e:
            results['error'] = f"Timeout: {str(e)}"
            logger.error(f"❌ Timeout: {str(e)}")
        
        except Exception as e:
            results['error'] = str(e)
            logger.error(f"❌ Error: {str(e)}", exc_info=True)
        
        return results
    
    def _print_report(self, report: dict) -> None:
        """Print formatted test report."""
        print("\n" + "="*70)
        print("📊 FORM FILLING TEST REPORT")
        print("="*70)
        
        print(f"\nGeneral Information:")
        print(f"  Platform: {report.get('job_title', 'Unknown').upper()}")
        print(f"  Job Title: {report.get('job_title', 'N/A')}")
        print(f"  Company: {report.get('company_name', 'N/A')}")
        print(f"  Status: {report.get('status', 'UNKNOWN').upper()}")
        print(f"  Duration: {report.get('duration_seconds', 0):.1f}s")
        
        if report.get('form_stats'):
            stats = report['form_stats']
            print(f"\nForm Statistics:")
            print(f"  • Total Questions: {stats.get('total_questions', 0)}")
            print(f"  • Auto-Filled: {stats.get('auto_filled', 0)}")
            print(f"  • Skipped: {stats.get('skipped', 0)}")
            print(f"  • Failed: {stats.get('failed', 0)}")
            fill_rate = stats.get('fill_rate', 0)
            print(f"  • Fill Rate: {fill_rate*100:.1f}%")
            
            # Color-coded result
            if fill_rate >= 0.9:
                print(f"  ✅ Excellent auto-fill rate!")
            elif fill_rate >= 0.7:
                print(f"  ✓ Good auto-fill rate (needs minor human input)")
            elif fill_rate >= 0.5:
                print(f"  ⚠️ Moderate auto-fill rate (needs human review)")
            else:
                print(f"  ❌ Low auto-fill rate (manual form filling recommended)")
        
        if report.get('manual_answers_count', 0) > 0:
            print(f"\nManual Input Provided:")
            print(f"  • Questions: {report.get('manual_answers_count', 0)}")
            if report.get('manual_answers'):
                for q, a in list(report.get('manual_answers', {}).items())[:5]:
                    q_short = q[:40] + "..." if len(q) > 40 else q
                    a_short = a[:40] + "..." if len(a) > 40 else a
                    print(f"    ✓ {q_short} → {a_short}")
                
                if len(report.get('manual_answers', {})) > 5:
                    print(f"    ... and {len(report.get('manual_answers', {})) - 5} more")
        
        if report.get('error'):
            print(f"\n❌ Error: {report['error']}")
        
        print("="*70 + "\n")
    
    async def cleanup(self) -> None:
        """Close browser and cleanup."""
        if self.browser_manager and hasattr(self.browser_manager, 'browser'):
            if self.browser_manager.browser:
                await self.browser_manager.browser.close()
                logger.info("✓ Browser closed")


async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(
        description='Test form fillers with real job postings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test Naukri job (dry-run)
  python test_real_job_posting.py --url "https://www.naukri.com/job-details-..." --portal naukri --dry-run

  # Test LinkedIn job with auto-fill
  python test_real_job_posting.py --url "https://www.linkedin.com/jobs/12345/" --portal linkedin

  # Test with headed browser (see what's happening)
  python test_real_job_posting.py --url "..." --no-headless

  # Test with auto-submit (CAUTION: will submit form!)
  python test_real_job_posting.py --url "..." --auto-submit
        """
    )
    
    parser.add_argument(
        '--url',
        required=True,
        help='Job posting URL (LinkedIn or Naukri)'
    )
    parser.add_argument(
        '--portal',
        choices=['linkedin', 'naukri'],
        default='naukri',
        help='Job portal (default: naukri)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only detect questions without filling'
    )
    parser.add_argument(
        '--auto-submit',
        action='store_true',
        help='Submit form after filling (CAUTION!)'
    )
    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Run browser in headed mode (see what\'s happening)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    tester = RealJobPostingTester(
        portal=args.portal,
        headless=not args.no_headless
    )
    
    try:
        # Setup
        await tester.setup()
        
        # Test
        results = await tester.test_job_posting(
            job_url=args.url,
            dry_run=args.dry_run,
            auto_submit=args.auto_submit
        )
        
        # Print summary
        if results['success']:
            print("✅ Test completed successfully!")
            sys.exit(0)
        else:
            print(f"❌ Test failed: {results['error']}")
            sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("\n⏹ Test interrupted by user")
        sys.exit(130)
    
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
    
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
