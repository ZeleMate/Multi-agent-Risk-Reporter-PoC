# Prompts Module

This module contains LLM prompts for the multi-agent risk reporter system.

## Structure

- `analyzer.py` - Risk identification prompts
- `verifier.py` - Evidence validation prompts
- `composer.py` - Report composition prompts

## Agent Prompts

### 1. Analyzer Agent (`analyzer.py`)
- **Purpose**: Identify and classify risks (UHPAI, ERB)
- **Functions**: `get_analyzer_prompt()`, `get_analyzer_system_prompt()`

### 2. Verifier Agent (`verifier.py`)
- **Purpose**: Validate evidence and ensure accuracy
- **Functions**: `get_verifier_prompt()`, `get_verifier_system_prompt()`

### 3. Composer Agent (`composer.py`)
- **Purpose**: Create executive reports
- **Functions**: `get_composer_prompt()`, `get_composer_system_prompt()`

## Usage

```python
from src.prompts.analyzer import get_analyzer_prompt
from src.prompts.verifier import get_verifier_prompt
from src.prompts.composer import get_composer_prompt

# Get prompts for agents
analyzer_prompt = get_analyzer_prompt(chunks, project_context)
verifier_prompt = get_verifier_prompt(candidates, evidence)
composer_prompt = get_composer_prompt(risks, project_context)
```
