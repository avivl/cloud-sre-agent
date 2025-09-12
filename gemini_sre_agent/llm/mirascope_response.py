# gemini_sre_agent/llm/mirascope_response.py

"""
Mirascope Response Processing Module

This module provides comprehensive response processing, validation, and
transformation capabilities for Mirascope provider responses.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from .mirascope_client import ClientResponse

T = TypeVar("T", bound=BaseModel)


class ResponseStatus(Enum):
    """Status of response processing."""

    SUCCESS = "success"
    VALIDATION_ERROR = "validation_error"
    PARSING_ERROR = "parsing_error"
    TRANSFORMATION_ERROR = "transformation_error"
    UNKNOWN_ERROR = "unknown_error"


class ResponseQuality(Enum):
    """Quality assessment of response."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"


@dataclass
class ResponseMetadata:
    """Metadata about response processing."""

    processing_time_ms: float
    validation_passed: bool = True
    quality_score: float = 0.0
    quality_assessment: ResponseQuality = ResponseQuality.UNKNOWN
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    transformations_applied: List[str] = field(default_factory=list)
    confidence_score: float = 0.0


@dataclass
class ProcessedResponse:
    """Processed response with metadata."""

    original_response: ClientResponse
    processed_content: str
    status: ResponseStatus
    metadata: ResponseMetadata
    structured_data: Optional[Any] = None
    validation_results: Optional[Dict[str, Any]] = None


class ResponseValidator(ABC):
    """Abstract base class for response validators."""

    @abstractmethod
    def validate(self, response: ClientResponse) -> Dict[str, Any]:
        """Validate a response and return validation results."""
        pass


class ContentLengthValidator(ResponseValidator):
    """Validates response content length."""

    def __init__(self, min_length: int = 1, max_length: int = 10000) -> None:
        self.min_length = min_length
        self.max_length = max_length

    def validate(self, response: ClientResponse) -> Dict[str, Any]:
        """Validate content length."""
        content_length = len(response.content)

        return {
            "valid": self.min_length <= content_length <= self.max_length,
            "content_length": content_length,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "error": (
                None
                if self.min_length <= content_length <= self.max_length
                else f"Content length {content_length} not in range [{self.min_length}, {self.max_length}]"
            ),
        }


class JSONStructureValidator(ResponseValidator):
    """Validates JSON structure in responses."""

    def __init__(self, required_fields: Optional[List[str]] = None) -> None:
        self.required_fields = required_fields or []

    def validate(self, response: ClientResponse) -> Dict[str, Any]:
        """Validate JSON structure."""
        try:
            data = json.loads(response.content)

            if not isinstance(data, dict):
                return {
                    "valid": False,
                    "error": "Response is not a JSON object",
                    "parsed_data": data,
                }

            missing_fields = []
            for field in self.required_fields:
                if field not in data:
                    missing_fields.append(field)

            return {
                "valid": len(missing_fields) == 0,
                "parsed_data": data,
                "missing_fields": missing_fields,
                "error": (
                    f"Missing required fields: {missing_fields}"
                    if missing_fields
                    else None
                ),
            }

        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "error": f"Invalid JSON: {str(e)}",
                "parsed_data": None,
            }


class RegexPatternValidator(ResponseValidator):
    """Validates response against regex patterns."""

    def __init__(self, patterns: Dict[str, str]: str) -> None:
        self.patterns = {
            name: re.compile(pattern) for name, pattern in patterns.items()
        }

    def validate(self, response: ClientResponse) -> Dict[str, Any]:
        """Validate against regex patterns."""
        results = {}
        all_valid = True

        for name, pattern in self.patterns.items():
            match = pattern.search(response.content)
            results[name] = {
                "matched": match is not None,
                "match": match.group() if match else None,
            }
            if not match:
                all_valid = False

        return {
            "valid": all_valid,
            "pattern_results": results,
            "error": None if all_valid else "Some patterns did not match",
        }


class ResponseTransformer(ABC):
    """Abstract base class for response transformers."""

    @abstractmethod
    def transform(self, response: ClientResponse) -> str:
        """Transform response content."""
        pass


class TextCleanerTransformer(ResponseTransformer):
    """Cleans and normalizes text content."""

    def __init__(
        self, remove_extra_whitespace: bool = True, normalize_quotes: bool = True
    ):
        self.remove_extra_whitespace = remove_extra_whitespace
        self.normalize_quotes = normalize_quotes

    def transform(self, response: ClientResponse) -> str:
        """Clean text content."""
        content = response.content

        if self.remove_extra_whitespace:
            content = re.sub(r"\s+", " ", content).strip()

        if self.normalize_quotes:
            content = content.replace('"', '"').replace('"', '"')
            content = content.replace("'", "'").replace("'", "'")

        return content


class JSONFormatterTransformer(ResponseTransformer):
    """Formats JSON content with proper indentation."""

    def __init__(self, indent: int = 2) -> None:
        self.indent = indent

    def transform(self, response: ClientResponse) -> str:
        """Format JSON content."""
        try:
            data = json.loads(response.content)
            return json.dumps(data, indent=self.indent, ensure_ascii=False)
        except json.JSONDecodeError:
            return response.content


class MarkdownFormatterTransformer(ResponseTransformer):
    """Formats content as Markdown."""

    def __init__(self, add_headers: bool = True, wrap_code: bool = True) -> None:
        self.add_headers = add_headers
        self.wrap_code = wrap_code

    def transform(self, response: ClientResponse) -> str:
        """Format content as Markdown."""
        content = response.content

        if self.add_headers and not content.startswith("#"):
            content = f"# Response\n\n{content}"

        if self.wrap_code:
            # Wrap code-like content in code blocks
            code_pattern = r"`([^`]+)`"
            content = re.sub(code_pattern, r"```\n\1\n```", content)

        return content


class QualityAssessor:
    """Assesses the quality of responses."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def assess_quality(self, response: ClientResponse) -> tuple[ResponseQuality, float]:
        """Assess response quality and return quality level and score."""
        score = 0.0
        factors = []

        # Content length factor
        content_length = len(response.content)
        if content_length > 0:
            length_score = min(1.0, content_length / 1000)  # Normalize to 0-1
            score += length_score * 0.2
            factors.append(f"length: {length_score:.2f}")

        # Token efficiency factor
        if response.tokens_used and response.tokens_used > 0:
            efficiency = content_length / response.tokens_used
            efficiency_score = min(1.0, efficiency / 10)  # Normalize
            score += efficiency_score * 0.2
            factors.append(f"efficiency: {efficiency_score:.2f}")

        # Cost efficiency factor
        if response.cost_usd and response.cost_usd > 0:
            cost_efficiency = content_length / (
                response.cost_usd * 1000
            )  # chars per dollar
            cost_score = min(1.0, cost_efficiency / 1000)  # Normalize
            score += cost_score * 0.1
            factors.append(f"cost_efficiency: {cost_score:.2f}")

        # Content structure factor
        structure_score = self._assess_structure(response.content)
        score += structure_score * 0.3
        factors.append(f"structure: {structure_score:.2f}")

        # Coherence factor
        coherence_score = self._assess_coherence(response.content)
        score += coherence_score * 0.2
        factors.append(f"coherence: {coherence_score:.2f}")

        # Determine quality level
        if score >= 0.8:
            quality = ResponseQuality.EXCELLENT
        elif score >= 0.6:
            quality = ResponseQuality.GOOD
        elif score >= 0.4:
            quality = ResponseQuality.FAIR
        else:
            quality = ResponseQuality.POOR

        self.logger.debug(
            f"Quality assessment: {quality.value} (score: {score:.2f}) - {', '.join(factors)}"
        )

        return quality, score

    def _assess_structure(self, content: str) -> float:
        """Assess content structure quality."""
        score = 0.0

        # Check for proper sentence structure
        sentences = re.split(r"[.!?]+", content)
        if len(sentences) > 1:
            score += 0.3

        # Check for paragraph structure
        paragraphs = content.split("\n\n")
        if len(paragraphs) > 1:
            score += 0.2

        # Check for list structure
        if re.search(r"^\s*[-*]\s", content, re.MULTILINE):
            score += 0.2

        # Check for code blocks
        if "```" in content or "`" in content:
            score += 0.1

        # Check for headers
        if re.search(r"^#+\s", content, re.MULTILINE):
            score += 0.2

        return min(1.0, score)

    def _assess_coherence(self, content: str) -> float:
        """Assess content coherence."""
        score = 0.0

        # Check for transition words
        transition_words = [
            "however",
            "therefore",
            "furthermore",
            "moreover",
            "additionally",
            "consequently",
        ]
        transition_count = sum(
            1 for word in transition_words if word.lower() in content.lower()
        )
        score += min(0.3, transition_count * 0.1)

        # Check for repetition (negative factor)
        words = content.lower().split()
        if len(words) > 0:
            unique_words = len(set(words))
            repetition_ratio = unique_words / len(words)
            score += repetition_ratio * 0.4

        # Check for proper capitalization
        sentences = re.split(r"[.!?]+", content)
        proper_caps = sum(1 for s in sentences if s.strip() and s.strip()[0].isupper())
        if len(sentences) > 0:
            caps_ratio = proper_caps / len(sentences)
            score += caps_ratio * 0.3

        return min(1.0, score)


class ResponseProcessor:
    """Main response processor with validation, transformation, and quality assessment."""

    def __init__(self) -> None:
        self.validators: List[ResponseValidator] = []
        self.transformers: List[ResponseTransformer] = []
        self.quality_assessor = QualityAssessor()
        self.logger = logging.getLogger(__name__)

    def add_validator(self, validator: ResponseValidator) -> None:
        """Add a response validator."""
        self.validators.append(validator)

    def add_transformer(self, transformer: ResponseTransformer) -> None:
        """Add a response transformer."""
        self.transformers.append(transformer)

    def process_response(
        self,
        response: ClientResponse,
        validate: bool = True,
        transform: bool = True,
        assess_quality: bool = True,
    ) -> ProcessedResponse:
        """Process a response with validation, transformation, and quality assessment."""
        start_time = datetime.now()

        processed_content = response.content
        status = ResponseStatus.SUCCESS
        validation_results = {}
        warnings = []
        errors = []
        transformations_applied = []

        # Validation
        if validate:
            for validator in self.validators:
                try:
                    result = validator.validate(response)
                    validation_results[validator.__class__.__name__] = result

                    if not result.get("valid", True):
                        errors.append(result.get("error", "Validation failed"))
                        status = ResponseStatus.VALIDATION_ERROR
                except Exception as e:
                    error_msg = (
                        f"Validator {validator.__class__.__name__} failed: {str(e)}"
                    )
                    errors.append(error_msg)
                    self.logger.warning(error_msg)

        # Transformation
        if transform and status == ResponseStatus.SUCCESS:
            for transformer in self.transformers:
                try:
                    old_content = processed_content
                    processed_content = transformer.transform(
                        ClientResponse(
                            content=processed_content,
                            model=response.model,
                            provider=response.provider,
                            request_id=response.request_id,
                            tokens_used=response.tokens_used,
                            cost_usd=response.cost_usd,
                            metadata=response.metadata,
                        )
                    )

                    if processed_content != old_content:
                        transformations_applied.append(transformer.__class__.__name__)
                except Exception as e:
                    error_msg = (
                        f"Transformer {transformer.__class__.__name__} failed: {str(e)}"
                    )
                    errors.append(error_msg)
                    status = ResponseStatus.TRANSFORMATION_ERROR
                    self.logger.warning(error_msg)

        # Quality assessment
        quality = ResponseQuality.UNKNOWN
        quality_score = 0.0
        if assess_quality:
            try:
                quality, quality_score = self.quality_assessor.assess_quality(response)
            except Exception as e:
                warnings.append(f"Quality assessment failed: {str(e)}")
                self.logger.warning(f"Quality assessment failed: {e}")

        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        # Create metadata
        metadata = ResponseMetadata(
            processing_time_ms=processing_time,
            validation_passed=len(errors) == 0,
            quality_score=quality_score,
            quality_assessment=quality,
            warnings=warnings,
            errors=errors,
            transformations_applied=transformations_applied,
            confidence_score=quality_score,
        )

        return ProcessedResponse(
            original_response=response,
            processed_content=processed_content,
            status=status,
            metadata=metadata,
            validation_results=validation_results,
        )

    def process_structured_response(
        self, response: ClientResponse, response_model: Type[T], validate: bool = True
    ) -> tuple[ProcessedResponse, Optional[T]]:
        """Process a response and attempt to parse it into a structured model."""
        processed = self.process_response(response, validate=validate, transform=False)

        structured_data = None
        if processed.status == ResponseStatus.SUCCESS:
            try:
                # Try to parse as JSON first
                data = json.loads(processed.processed_content)
                structured_data = response_model(**data)
            except (json.JSONDecodeError, ValidationError) as e:
                processed.metadata.errors.append(
                    f"Failed to parse structured data: {str(e)}"
                )
                processed.status = ResponseStatus.PARSING_ERROR
                self.logger.warning(f"Failed to parse structured response: {e}")

        return processed, structured_data

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get statistics about response processing."""
        return {
            "validators_count": len(self.validators),
            "transformers_count": len(self.transformers),
            "validator_types": [v.__class__.__name__ for v in self.validators],
            "transformer_types": [t.__class__.__name__ for t in self.transformers],
        }


class ResponseProcessorFactory:
    """Factory for creating configured response processors."""

    @staticmethod
    def create_default_processor() -> ResponseProcessor:
        """Create a processor with default validators and transformers."""
        processor = ResponseProcessor()

        # Add default validators
        processor.add_validator(ContentLengthValidator())
        processor.add_validator(JSONStructureValidator())

        # Add default transformers
        processor.add_transformer(TextCleanerTransformer())
        processor.add_transformer(JSONFormatterTransformer())

        return processor

    @staticmethod
    def create_json_processor() -> ResponseProcessor:
        """Create a processor optimized for JSON responses."""
        processor = ResponseProcessor()

        processor.add_validator(ContentLengthValidator())
        processor.add_validator(JSONStructureValidator())
        processor.add_transformer(JSONFormatterTransformer())

        return processor

    @staticmethod
    def create_text_processor() -> ResponseProcessor:
        """Create a processor optimized for text responses."""
        processor = ResponseProcessor()

        processor.add_validator(ContentLengthValidator())
        processor.add_transformer(TextCleanerTransformer())
        processor.add_transformer(MarkdownFormatterTransformer())

        return processor

    @staticmethod
    def create_custom_processor(
        validators: Optional[List[ResponseValidator]] = None,
        transformers: Optional[List[ResponseTransformer]] = None,
    ) -> ResponseProcessor:
        """Create a processor with custom validators and transformers."""
        processor = ResponseProcessor()

        if validators:
            for validator in validators:
                processor.add_validator(validator)

        if transformers:
            for transformer in transformers:
                processor.add_transformer(transformer)

        return processor


# Global response processor instance
_response_processor: Optional[ResponseProcessor] = None


def get_response_processor() -> ResponseProcessor:
    """Get the global response processor instance."""
    global _response_processor
    if _response_processor is None:
        _response_processor = ResponseProcessorFactory.create_default_processor()
    return _response_processor
