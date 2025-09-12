# gemini_sre_agent/ml/workflow/workflow_generation.py

"""
Workflow generation module for the unified workflow orchestrator.

This module handles generation operations within the workflow, including
code generation, prompt generation, and solution generation.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..enhanced_remediation_agent import EnhancedRemediationAgentV2
from ...llm.config import LLMConfig
from ...llm.base import ModelType
from ..prompt_context_models import IssueContext, RepositoryContext
from ...core.interfaces import ProcessableComponent
from ...core.types import ConfigDict, Timestamp

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """
    Result of workflow generation operations.
    
    This class holds the results of generation operations including
    generated code, prompts, and solutions.
    """
    
    # Generation metadata
    generation_id: str
    workflow_id: str
    generation_type: str
    timestamp: Timestamp
    
    # Generation results
    generated_content: str
    code_patches: List[Dict[str, Any]]
    prompts: List[str]
    solutions: List[str]
    confidence_score: float
    
    # Performance metrics
    generation_duration: float
    content_length: int
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert generation result to dictionary."""
        return {
            "generation_id": self.generation_id,
            "workflow_id": self.workflow_id,
            "generation_type": self.generation_type,
            "timestamp": self.timestamp,
            "generated_content": self.generated_content,
            "code_patches": self.code_patches,
            "prompts": self.prompts,
            "solutions": self.solutions,
            "confidence_score": self.confidence_score,
            "generation_duration": self.generation_duration,
            "content_length": self.content_length,
            "success": self.success,
            "error_message": self.error_message,
        }


class WorkflowGenerationEngine(ProcessableComponent[Dict[str, Any], GenerationResult]):
    """
    Generation engine for workflow operations.
    
    This class handles all generation operations within the workflow,
    including code generation, prompt generation, and solution generation.
    """
    
    def __init__(
        self,
        component_id: str = "workflow_generation_engine",
        name: str = "Workflow Generation Engine",
        config: Optional[ConfigDict] = None
    ) -> None:
        """
        Initialize the workflow generation engine.
        
        Args:
            component_id: Unique identifier for the component
            name: Human-readable name for the component
            config: Optional initial configuration
        """
        super().__init__(component_id, name, config)
        
        # Initialize remediation agent with default config
        llm_config = LLMConfig(
            default_provider="gemini",
            default_model_type=ModelType.SMART,
            enable_fallback=True,
            enable_monitoring=True
        )
        self.remediation_agent = EnhancedRemediationAgentV2(
            llm_config=llm_config,
            agent_name="workflow_generation_agent"
        )
        
        # Generation tracking
        self.generation_count = 0
        self.total_generation_time = 0.0
        self.successful_generations = 0
        self.failed_generations = 0
        self.error_count = 0
    
    async def generate_code(
        self,
        issue_context: IssueContext,
        repository_context: RepositoryContext,
        workflow_id: str,
        generation_type: str = "code_fix"
    ) -> GenerationResult:
        """
        Generate code solutions for an issue.
        
        Args:
            issue_context: Issue context to generate code for
            repository_context: Repository context
            workflow_id: Workflow identifier
            generation_type: Type of code generation to perform
            
        Returns:
            Generation result
        """
        start_time = time.time()
        generation_id = f"code_gen_{workflow_id}_{int(time.time())}"
        
        try:
            logger.info(f"Starting {generation_type} code generation for workflow {workflow_id}")
            
            # Create triage data from issue context
            triage_data = {
                "issue_type": issue_context.issue_type.value,
                "affected_files": issue_context.affected_files,
                "severity_level": issue_context.severity_level,
                "error_patterns": issue_context.error_patterns,
                "impact_analysis": issue_context.impact_analysis,
            }
            
            # Create historical logs (empty for now)
            historical_logs = []
            
            # Create configs from repository context
            configs = {
                "architecture_type": repository_context.architecture_type,
                "technology_stack": repository_context.technology_stack,
                "coding_standards": repository_context.coding_standards,
            }
            
            # Perform code generation using the enhanced remediation agent
            remediation_response = await self.remediation_agent.generate_remediation(
                triage_data=triage_data,
                historical_logs=historical_logs,
                configs=configs,
                flow_id=workflow_id
            )
            
            # Extract generated content
            generated_content = self._extract_generated_content(remediation_response)
            code_patches = self._extract_code_patches(remediation_response)
            prompts = self._extract_prompts(remediation_response)
            solutions = self._extract_solutions(remediation_response)
            confidence_score = self._calculate_confidence(remediation_response)
            
            generation_duration = time.time() - start_time
            
            result = GenerationResult(
                generation_id=generation_id,
                workflow_id=workflow_id,
                generation_type=generation_type,
                timestamp=time.time(),
                generated_content=generated_content,
                code_patches=code_patches,
                prompts=prompts,
                solutions=solutions,
                confidence_score=confidence_score,
                generation_duration=generation_duration,
                content_length=len(generated_content),
                success=True,
            )
            
            # Update metrics
            self.generation_count += 1
            self.total_generation_time += generation_duration
            self.successful_generations += 1
            
            logger.info(f"Completed code generation {generation_id} in {generation_duration:.3f}s")
            return result
            
        except Exception as e:
            generation_duration = time.time() - start_time
            error_msg = f"Code generation failed: {str(e)}"
            
            logger.error(f"Code generation {generation_id} failed: {error_msg}")
            
            result = GenerationResult(
                generation_id=generation_id,
                workflow_id=workflow_id,
                generation_type=generation_type,
                timestamp=time.time(),
                generated_content="",
                code_patches=[],
                prompts=[],
                solutions=[],
                confidence_score=0.0,
                generation_duration=generation_duration,
                content_length=0,
                success=False,
                error_message=error_msg,
            )
            
            # Update metrics
            self.generation_count += 1
            self.total_generation_time += generation_duration
            self.failed_generations += 1
            
            return result
    
    async def generate_prompts(
        self,
        context: Dict[str, Any],
        workflow_id: str,
        prompt_type: str = "analysis"
    ) -> GenerationResult:
        """
        Generate prompts for analysis or other operations.
        
        Args:
            context: Context for prompt generation
            workflow_id: Workflow identifier
            prompt_type: Type of prompt to generate
            
        Returns:
            Generation result
        """
        start_time = time.time()
        generation_id = f"prompt_gen_{workflow_id}_{int(time.time())}"
        
        try:
            logger.info(f"Starting {prompt_type} prompt generation for workflow {workflow_id}")
            
            # Create triage data from context
            triage_data = {
                "context": context,
                "prompt_type": prompt_type,
                "generation_type": "prompt_generation",
            }
            
            # Create historical logs (empty for now)
            historical_logs = []
            
            # Create configs (empty for now)
            configs = {}
            
            # Perform prompt generation using the enhanced remediation agent
            remediation_response = await self.remediation_agent.generate_remediation(
                triage_data=triage_data,
                historical_logs=historical_logs,
                configs=configs,
                flow_id=workflow_id
            )
            
            # Extract generated content
            generated_content = self._extract_generated_content(remediation_response)
            code_patches = self._extract_code_patches(remediation_response)
            prompts = self._extract_prompts(remediation_response)
            solutions = self._extract_solutions(remediation_response)
            confidence_score = self._calculate_confidence(remediation_response)
            
            generation_duration = time.time() - start_time
            
            result = GenerationResult(
                generation_id=generation_id,
                workflow_id=workflow_id,
                generation_type=f"prompt_{prompt_type}",
                timestamp=time.time(),
                generated_content=generated_content,
                code_patches=code_patches,
                prompts=prompts,
                solutions=solutions,
                confidence_score=confidence_score,
                generation_duration=generation_duration,
                content_length=len(generated_content),
                success=True,
            )
            
            # Update metrics
            self.generation_count += 1
            self.total_generation_time += generation_duration
            self.successful_generations += 1
            
            logger.info(f"Completed prompt generation {generation_id} in {generation_duration:.3f}s")
            return result
            
        except Exception as e:
            generation_duration = time.time() - start_time
            error_msg = f"Prompt generation failed: {str(e)}"
            
            logger.error(f"Prompt generation {generation_id} failed: {error_msg}")
            
            result = GenerationResult(
                generation_id=generation_id,
                workflow_id=workflow_id,
                generation_type=f"prompt_{prompt_type}",
                timestamp=time.time(),
                generated_content="",
                code_patches=[],
                prompts=[],
                solutions=[],
                confidence_score=0.0,
                generation_duration=generation_duration,
                content_length=0,
                success=False,
                error_message=error_msg,
            )
            
            # Update metrics
            self.generation_count += 1
            self.total_generation_time += generation_duration
            self.failed_generations += 1
            
            return result
    
    def process(self, input_data: Dict[str, Any]) -> GenerationResult:
        """
        Process generation request (synchronous wrapper).
        
        Args:
            input_data: Generation request data
            
        Returns:
            Generation result
        """
        # This is a synchronous wrapper for the async methods
        # In practice, this would be called from an async context
        raise NotImplementedError("Use async methods for generation operations")
    
    def initialize(self) -> None:
        """Initialize the component."""
        self._status = "initialized"
        logger.info(f"Initialized {self.name}")
    
    def shutdown(self) -> None:
        """Shutdown the component."""
        self._status = "shutdown"
        logger.info(f"Shutdown {self.name}")
    
    def configure(self, config: ConfigDict) -> None:
        """
        Configure the component with new settings.
        
        Args:
            config: Configuration dictionary
        """
        self._config.update(config)
        logger.info(f"Configured {self.name}")
    
    def validate_config(self, config: ConfigDict) -> bool:
        """
        Validate a configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if valid, False otherwise
        """
        return isinstance(config, dict)
    
    def set_state(self, key: str, value: Any) -> None:
        """
        Set a state value.
        
        Args:
            key: State key
            value: State value
        """
        self._state[key] = value
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """
        Get a state value.
        
        Args:
            key: State key
            default: Default value if key not found
            
        Returns:
            State value or default
        """
        return self._state.get(key, default)
    
    def clear_state(self, key: Optional[str] = None) -> None:
        """
        Clear state values.
        
        Args:
            key: Specific key to clear, or None to clear all
        """
        if key is None:
            self._state.clear()
        else:
            self._state.pop(key, None)
    
    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect component metrics.
        
        Returns:
            Dictionary containing metrics
        """
        return self.get_generation_metrics()
    
    def _extract_generated_content(self, remediation_response: Any) -> str:
        """
        Extract generated content from remediation response.
        
        Args:
            remediation_response: Response from remediation agent
            
        Returns:
            Generated content string
        """
        try:
            if hasattr(remediation_response, 'generated_content'):
                return remediation_response.generated_content
            elif hasattr(remediation_response, 'content'):
                return remediation_response.content
            elif hasattr(remediation_response, 'description'):
                return remediation_response.description
            elif isinstance(remediation_response, dict) and 'content' in remediation_response:
                return remediation_response['content']
            else:
                return str(remediation_response)
        except Exception as e:
            logger.warning(f"Failed to extract generated content: {e}")
            return ""
    
    def _extract_code_patches(self, remediation_response: Any) -> List[Dict[str, Any]]:
        """
        Extract code patches from remediation response.
        
        Args:
            remediation_response: Response from remediation agent
            
        Returns:
            List of code patches
        """
        try:
            if hasattr(remediation_response, 'code_patches'):
                return remediation_response.code_patches
            elif hasattr(remediation_response, 'patches'):
                return remediation_response.patches
            elif isinstance(remediation_response, dict) and 'code_patches' in remediation_response:
                return remediation_response['code_patches']
            else:
                return []
        except Exception as e:
            logger.warning(f"Failed to extract code patches: {e}")
            return []
    
    def _extract_prompts(self, remediation_response: Any) -> List[str]:
        """
        Extract prompts from remediation response.
        
        Args:
            remediation_response: Response from remediation agent
            
        Returns:
            List of prompts
        """
        try:
            if hasattr(remediation_response, 'prompts'):
                return remediation_response.prompts
            elif hasattr(remediation_response, 'suggested_prompts'):
                return remediation_response.suggested_prompts
            elif isinstance(remediation_response, dict) and 'prompts' in remediation_response:
                return remediation_response['prompts']
            else:
                return []
        except Exception as e:
            logger.warning(f"Failed to extract prompts: {e}")
            return []
    
    def _extract_solutions(self, remediation_response: Any) -> List[str]:
        """
        Extract solutions from remediation response.
        
        Args:
            remediation_response: Response from remediation agent
            
        Returns:
            List of solutions
        """
        try:
            if hasattr(remediation_response, 'solutions'):
                return remediation_response.solutions
            elif hasattr(remediation_response, 'recommended_solutions'):
                return remediation_response.recommended_solutions
            elif isinstance(remediation_response, dict) and 'solutions' in remediation_response:
                return remediation_response['solutions']
            else:
                return []
        except Exception as e:
            logger.warning(f"Failed to extract solutions: {e}")
            return []
    
    def _calculate_confidence(self, remediation_response: Any) -> float:
        """
        Calculate confidence score from remediation response.
        
        Args:
            remediation_response: Response from remediation agent
            
        Returns:
            Confidence score (0.0-1.0)
        """
        try:
            if hasattr(remediation_response, 'confidence'):
                return float(remediation_response.confidence)
            elif hasattr(remediation_response, 'confidence_score'):
                return float(remediation_response.confidence_score)
            elif isinstance(remediation_response, dict) and 'confidence' in remediation_response:
                return float(remediation_response['confidence'])
            else:
                return 0.5  # Default confidence
        except Exception as e:
            logger.warning(f"Failed to calculate confidence: {e}")
            return 0.5
    
    def get_generation_metrics(self) -> Dict[str, Any]:
        """
        Get generation performance metrics.
        
        Returns:
            Dictionary containing generation metrics
        """
        return {
            "total_generations": self.generation_count,
            "successful_generations": self.successful_generations,
            "failed_generations": self.failed_generations,
            "success_rate": (self.successful_generations / self.generation_count * 100) if self.generation_count > 0 else 0.0,
            "total_generation_time": self.total_generation_time,
            "average_generation_time": (self.total_generation_time / self.generation_count) if self.generation_count > 0 else 0.0,
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get the component's health status.
        
        Returns:
            Dictionary containing health status information
        """
        metrics = self.get_generation_metrics()
        
        return {
            "component_id": self.component_id,
            "name": self.name,
            "status": self.status,
            "healthy": self.check_health(),
            "generation_metrics": metrics,
            "processing_count": self.processing_count,
            "last_processed_at": self.last_processed_at,
        }
    
    def check_health(self) -> bool:
        """
        Check if the component is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        return (
            self.status != "error" and
            self.error_count == 0 and
            self.failed_generations < self.successful_generations  # More successes than failures
        )
