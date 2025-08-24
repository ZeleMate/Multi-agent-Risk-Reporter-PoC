"""
LLM Service for OpenAI integration.
Provides chat_json and compose interfaces for agents.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import get_config

# Import prompts
try:
    from ..prompts import get_analyzer_prompt, get_verifier_prompt, get_composer_prompt
except ImportError:
    # Fallback for testing
    def get_analyzer_prompt(chunks, context=""): return "Analyzer prompt"
    def get_verifier_prompt(candidates, evidence): return "Verifier prompt"
    def get_composer_prompt(risks, context=""): return "Composer prompt"

logger = logging.getLogger(__name__)

class LLMService:
    """
    OpenAI LLM service with chat_json and compose interfaces.
    """

    def __init__(self, model_config: Optional[str] = None):
        """Initialize LLM service with configuration."""
        self.config = get_config()
        self.client = OpenAI(api_key=self.config.openai_api_key)

        # Determine which model to use
        if model_config == "alternative_model":
            self.model_name = self.config.alternative_model.chat_model
            self.temperature = self.config.alternative_model.temperature
            self.max_tokens = self.config.alternative_model.max_output_tokens
        else:
            self.model_name = self.config.model.chat_model
            self.temperature = self.config.model.temperature
            self.max_tokens = self.config.model.max_output_tokens

        logger.info(f"LLM Service initialized with model: {self.model_name}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def chat_json(self, messages: List[Dict[str, str]], response_format: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Chat completion with JSON response format.
        Based on OpenAI API for structured outputs.

        Args:
            messages: List of message dictionaries
            response_format: JSON schema for response format

        Returns:
            Parsed JSON response
        """
        try:
            # Prepare the request
            request_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }

            # Add response format if specified
            if response_format:
                request_params["response_format"] = {"type": "json_object"}

            # Make the API call
            response = self.client.chat.completions.create(**request_params)

            # Extract and parse the response
            content = response.choices[0].message.content

            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {content}")
                raise ValueError(f"Invalid JSON response: {e}")

        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def compose(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Simple text generation for report composition.

        Args:
            prompt: The prompt text
            context: Optional context dictionary

        Returns:
            Generated text response
        """
        try:
            messages = [
                {"role": "system", "content": "You are a professional report writer. Generate high-quality, well-structured text."},
                {"role": "user", "content": prompt}
            ]

            # Add context if provided
            if context:
                context_str = f"\n\nContext: {json.dumps(context, indent=2)}"
                messages[-1]["content"] += context_str

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Compose API call failed: {e}")
            raise

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model configuration."""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "provider": "openai"
        }

    def analyze_risks(self, chunks: List[Dict[str, Any]], project_context: str = "") -> Dict[str, Any]:
        """
        Analyze chunks for risks using analyzer prompt.

        Args:
            chunks: Evidence chunks to analyze
            project_context: Additional project context

        Returns:
            JSON response from analyzer
        """
        prompt = get_analyzer_prompt(chunks, project_context)

        messages = [
            {"role": "system", "content": "You are a risk analysis expert. Analyze the provided evidence and return JSON with identified risks."},
            {"role": "user", "content": prompt}
        ]

        return self.chat_json(messages, response_format={"type": "json_object"})

    def verify_risks(self, candidates: List[Dict[str, Any]], full_evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify risk candidates using verifier prompt.

        Args:
            candidates: Risk candidates from analyzer
            full_evidence: Full evidence chunks for validation

        Returns:
            JSON response from verifier
        """
        prompt = get_verifier_prompt(candidates, full_evidence)

        messages = [
            {"role": "system", "content": "You are an evidence verification expert. Validate each risk claim against the provided evidence."},
            {"role": "user", "content": prompt}
        ]

        return self.chat_json(messages, response_format={"type": "json_object"})

    def compose_report(self, verified_risks: List[Dict[str, Any]], project_context: str = "") -> str:
        """
        Compose executive report using composer prompt.

        Args:
            verified_risks: Verified risks from verifier
            project_context: Additional project context

        Returns:
            Markdown report from composer
        """
        prompt = get_composer_prompt(verified_risks, project_context)

        messages = [
            {"role": "system", "content": "You are an executive report writer. Create a professional risk report in Markdown format."},
            {"role": "user", "content": prompt}
        ]

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        return response.choices[0].message.content


# Convenience functions
def get_llm_service(model_config: Optional[str] = None) -> LLMService:
    """Get an instance of the LLM service."""
    return LLMService(model_config)

def chat_json(messages: List[Dict[str, str]], model_config: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function for JSON chat completion."""
    service = get_llm_service(model_config)
    return service.chat_json(messages)

def compose(prompt: str, context: Optional[Dict[str, Any]] = None, model_config: Optional[str] = None) -> str:
    """Convenience function for text composition."""
    service = get_llm_service(model_config)
    return service.compose(prompt, context)

# Agent-specific convenience functions
def analyze_risks(chunks: List[Dict[str, Any]], project_context: str = "", model_config: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function for risk analysis."""
    service = get_llm_service(model_config)
    return service.analyze_risks(chunks, project_context)

def verify_risks(candidates: List[Dict[str, Any]], full_evidence: Dict[str, Any], model_config: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function for risk verification."""
    service = get_llm_service(model_config)
    return service.verify_risks(candidates, full_evidence)

def compose_report(verified_risks: List[Dict[str, Any]], project_context: str = "", model_config: Optional[str] = None) -> str:
    """Convenience function for report composition."""
    service = get_llm_service(model_config)
    return service.compose_report(verified_risks, project_context)
