"""
Security Rules and Validation

Validates generated code for security issues before execution.
Blocks dangerous operations and imports.
"""

from typing import Tuple, List
import re
import structlog

logger = structlog.get_logger(__name__)


class SecurityValidator:
    """
    Validates code for security issues
    
    Blocks:
    - Dangerous imports (os.system, subprocess, eval, exec)
    - File system access outside workspace
    - Network access to unauthorized domains
    - Code injection attempts
    """
    
    # Blocked imports and functions
    BLOCKED_IMPORTS = [
        'os.system',
        'subprocess',
        'eval',
        'exec',
        '__import__',
        'compile',
        'open',  # File access
        'file',
        'input',  # User input
        'raw_input',
    ]
    
    # Blocked patterns
    BLOCKED_PATTERNS = [
        r'__.*__',  # Dunder methods (except common ones)
        r'globals\(',
        r'locals\(',
        r'vars\(',
        r'dir\(',
        r'getattr\(',
        r'setattr\(',
        r'delattr\(',
        r'hasattr\(',
    ]
    
    # Allowed imports
    ALLOWED_IMPORTS = [
        'json',
        'datetime',
        'time',
        'math',
        'random',
        'uuid',
        'typing',
        'asyncio',
        'mcp.servers',  # MCP tool imports
    ]
    
    def __init__(self):
        self.violations = []
    
    def validate(self, code: str) -> Tuple[bool, List[str]]:
        """
        Validate code for security issues
        
        Args:
            code: Python code to validate
            
        Returns:
            Tuple of (is_safe, list_of_violations)
        """
        self.violations = []
        
        # Check for blocked imports
        self._check_imports(code)
        
        # Check for blocked patterns
        self._check_patterns(code)
        
        # Check for dangerous operations
        self._check_dangerous_operations(code)
        
        is_safe = len(self.violations) == 0
        
        if not is_safe:
            logger.warning(
                "Code validation failed",
                violations=self.violations
            )
        
        return is_safe, self.violations
    
    def _check_imports(self, code: str):
        """Check for blocked imports"""
        import_lines = [
            line.strip() for line in code.split('\n')
            if line.strip().startswith(('import ', 'from '))
        ]
        
        for line in import_lines:
            # Check if import is blocked
            for blocked in self.BLOCKED_IMPORTS:
                if blocked in line:
                    self.violations.append(f"Blocked import: {blocked}")
            
            # Check if import is allowed
            is_allowed = False
            for allowed in self.ALLOWED_IMPORTS:
                if allowed in line:
                    is_allowed = True
                    break
            
            if not is_allowed and 'mcp.servers' not in line:
                self.violations.append(f"Unauthorized import: {line}")
    
    def _check_patterns(self, code: str):
        """Check for blocked patterns"""
        for pattern in self.BLOCKED_PATTERNS:
            matches = re.findall(pattern, code)
            if matches:
                # Allow common dunder methods
                allowed_dunders = ['__init__', '__str__', '__repr__', '__name__']
                for match in matches:
                    if match not in allowed_dunders:
                        self.violations.append(f"Blocked pattern: {match}")
    
    def _check_dangerous_operations(self, code: str):
        """Check for dangerous operations"""
        dangerous_keywords = [
            'rm -rf',
            'DROP TABLE',
            'DELETE FROM',
            'TRUNCATE',
            'ALTER TABLE',
            'CREATE USER',
            'GRANT',
            'REVOKE',
        ]
        
        code_upper = code.upper()
        for keyword in dangerous_keywords:
            if keyword in code_upper:
                self.violations.append(f"Dangerous operation: {keyword}")
    
    def tokenize_pii(self, data: str) -> str:
        """
        Tokenize PII in data
        
        Replaces:
        - Email addresses → [EMAIL_1], [EMAIL_2], etc.
        - Phone numbers → [PHONE_1], [PHONE_2], etc.
        - SSN → [SSN_1], [SSN_2], etc.
        """
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, data)
        for i, email in enumerate(emails, 1):
            data = data.replace(email, f'[EMAIL_{i}]')
        
        # Phone pattern (US format)
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phones = re.findall(phone_pattern, data)
        for i, phone in enumerate(phones, 1):
            data = data.replace(phone, f'[PHONE_{i}]')
        
        # SSN pattern
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        ssns = re.findall(ssn_pattern, data)
        for i, ssn in enumerate(ssns, 1):
            data = data.replace(ssn, f'[SSN_{i}]')
        
        return data
