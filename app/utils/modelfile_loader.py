"""
Utility for loading and parsing Modelfile content.
"""
import os
import re
from typing import Optional

def extract_system_prompt(modelfile_path: str) -> Optional[str]:
    """Extract the system prompt from a Modelfile.
    
    Args:
        modelfile_path: Path to the Modelfile
        
    Returns:
        Extracted system prompt text, or None if not found
    """
    if not os.path.exists(modelfile_path):
        return None
        
    with open(modelfile_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for the TEMPLATE block in the Modelfile
    template_match = re.search(
        r'TEMPLATE\s*[\'"`]([\s\S]*?)[\'"`]',
        content,
        re.MULTILINE
    )
    
    if not template_match:
        return None
        
    template = template_match.group(1)
    
    # Extract the system prompt from the template
    system_match = re.search(
        r'<\|start_header_id\|>system<\|end_header_id\|>([\s\S]*?)<\|eom\|>',
        template,
        re.MULTILINE
    )
    
    if system_match:
        return system_match.group(1).strip()
    return None

def get_default_system_prompt(modelfile_path: Optional[str] = None) -> str:
    """Get the default system prompt from the Modelfile.
    
    Args:
        modelfile_path: Optional path to the Modelfile. If not provided,
                       looks for the default path in the environment variable
                       AI_SYSTEM_PROMPT_PATH or uses a default location.
                       
    Returns:
        The system prompt string, or a default prompt if not found.
    """
    if modelfile_path is None:
        modelfile_path = os.getenv(
            'AI_SYSTEM_PROMPT_PATH',
            '/app/ollama/Modelfile.unibase-erp'  # Default container path
        )
    
    # Try to load from Modelfile
    system_prompt = extract_system_prompt(modelfile_path)
    
    if system_prompt:
        return system_prompt
    
    # Fallback default prompt
    return (
        "You are an AI assistant for the UNIBASE ERP system. "
        "Provide concise, factual responses based on the provided context. "
        "If you don't know the answer, say so rather than making up information."
    )
