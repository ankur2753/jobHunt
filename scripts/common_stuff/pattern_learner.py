"""
Pattern Learning and Human Fallback System
Learns from human actions and replicates patterns for automation
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ActionPattern:
    """Represents a recorded user action pattern."""
    
    def __init__(self, action_type: str, selector: str = None, text: str = None, details: dict = None):
        self.action_type = action_type  # 'click', 'fill', 'select', 'scroll', etc.
        self.selector = selector
        self.text = text
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            'action_type': self.action_type,
            'selector': self.selector,
            'text': self.text,
            'details': self.details,
            'timestamp': self.timestamp
        }


class PatternLearner:
    """Learns and stores interaction patterns from human actions."""
    
    def __init__(self, db_path: str = "pattern_db"):
        self.db_path = Path(db_path)
        self.db_path.mkdir(exist_ok=True)
        self.patterns_file = self.db_path / "naukri_patterns.json"
        self.current_job_id = None
        self.current_patterns = []
        self._load_patterns()
    
    def _load_patterns(self):
        """Load existing patterns from file."""
        if self.patterns_file.exists():
            try:
                with open(self.patterns_file, 'r') as f:
                    self.patterns = json.load(f)
                logger.info(f"Loaded {len(self.patterns)} existing patterns")
            except Exception as e:
                logger.error(f"Error loading patterns: {e}")
                self.patterns = {}
        else:
            self.patterns = {}
    
    def start_recording(self, job_id: str):
        """Start recording actions for a job."""
        self.current_job_id = job_id
        self.current_patterns = []
        logger.info(f"Started recording patterns for job: {job_id}")
    
    def record_action(self, action: ActionPattern):
        """Record a user action."""
        self.current_patterns.append(action)
        logger.debug(f"Recorded action: {action.action_type} - {action.selector}")
    
    def save_patterns(self):
        """Save patterns to file."""
        if not self.current_job_id or not self.current_patterns:
            return
        
        job_patterns = {
            'job_id': self.current_job_id,
            'patterns': [p.to_dict() for p in self.current_patterns],
            'timestamp': datetime.now().isoformat(),
            'count': len(self.current_patterns)
        }
        
        # Create a job-specific key
        job_key = f"job_{self.current_job_id}"
        self.patterns[job_key] = job_patterns
        
        try:
            with open(self.patterns_file, 'w') as f:
                json.dump(self.patterns, f, indent=2)
            logger.info(f"Saved {len(self.current_patterns)} patterns for {self.current_job_id}")
        except Exception as e:
            logger.error(f"Error saving patterns: {e}")
    
    def get_patterns_for_job(self, job_id: str) -> Optional[List[ActionPattern]]:
        """Get stored patterns for a job."""
        job_key = f"job_{job_id}"
        if job_key in self.patterns:
            job_data = self.patterns[job_key]
            return [ActionPattern(**p) for p in job_data.get('patterns', [])]
        return None
    
    def get_all_apply_patterns(self) -> List[Dict]:
        """Get all Apply button click patterns."""
        apply_patterns = []
        for job_key, job_data in self.patterns.items():
            patterns = job_data.get('patterns', [])
            apply_clicks = [p for p in patterns if p.get('action_type') == 'click' and 'apply' in str(p.get('selector', '')).lower()]
            if apply_clicks:
                apply_patterns.append({
                    'job_id': job_data.get('job_id'),
                    'patterns': apply_clicks
                })
        return apply_patterns
    
    def get_form_fill_patterns(self) -> Dict[str, str]:
        """Extract question-to-answer patterns from all recordings."""
        qa_patterns = {}
        for job_key, job_data in self.patterns.items():
            patterns = job_data.get('patterns', [])
            for pattern in patterns:
                if pattern.get('action_type') == 'fill_form':
                    question = pattern.get('details', {}).get('question')
                    answer = pattern.get('text')
                    if question and answer:
                        qa_patterns[question] = answer
        return qa_patterns


class HumanFallbackHandler:
    """Handles human intervention and learning from user actions."""
    
    def __init__(self, page, pattern_learner: PatternLearner):
        self.page = page
        self.pattern_learner = pattern_learner
    
    async def pause_for_human_intervention(self, task: str, job_id: str = None) -> bool:
        """
        Pause automation and let human take over.
        Returns True if user successfully completed the action, False otherwise.
        """
        if job_id:
            self.pattern_learner.start_recording(job_id)
        
        print("\n" + "="*60)
        print("🤝 HUMAN INTERVENTION REQUIRED")
        print("="*60)
        print(f"Task: {task}")
        print("\nPlease perform the action in the browser window.")
        print("Once you have completed the action, click OK or press Enter below.\n")
        
        input("Press Enter when done (or type 'skip' to skip this job): ")
        
        # Save recorded patterns
        self.pattern_learner.save_patterns()
        
        return True
    
    async def record_user_action(self, action_type: str, selector: str = None, 
                                text: str = None, details: dict = None):
        """Record a user action for pattern learning."""
        action = ActionPattern(action_type, selector, text, details)
        self.pattern_learner.record_action(action)
