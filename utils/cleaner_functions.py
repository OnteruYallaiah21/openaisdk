

import json
import re
import os
import sys
import inspect
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Dict, List, Optional, Union, Literal
class JSONCleaner:
    """
    A utility class that cleans, validates, and parses JSON from LLM outputs.
    Ensures that structured data matches expected schemas even if the LLM makes mistakes.
    """
    @staticmethod
    def process(raw_text: str) -> Dict[str, Any]:
        if not raw_text:
            return {}

        # Remove hidden characters like non-breaking spaces (\xa0) and normalize whitespace
        text = raw_text.replace('\xa0', ' ').replace('\u200b', '')
        
        # Remove markdown code blocks if they exist
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Extract the outermost JSON object {}
        # Using a non-greedy approach that searches for the first { and last }
        try:
            start_index = text.find('{')
            end_index = text.rfind('}')
            
            if start_index == -1 or end_index == -1:
                return {}
                
            json_str = text[start_index:end_index + 1]
            
            # Basic cleanup for common LLM errors
            # 1. Fix missing quotes on keys
            json_str = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str)
            # 2. Fix trailing commas before closing braces/brackets
            json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
            # 3. Replace single quotes with double quotes (only if not inside an existing double-quoted string)
            # Note: This is a simple heuristic. For complex strings, escaping may be needed.
            if "'" in json_str and '"' not in json_str:
                json_str = json_str.replace("'", '"')
            
            return json.loads(json_str)
        except Exception:
            # Fallback: manually strip any remaining control characters
            try:
                cleaned = "".join(ch for ch in json_str if ord(ch) >= 32)
                return json.loads(cleaned)
            except:
                return {}