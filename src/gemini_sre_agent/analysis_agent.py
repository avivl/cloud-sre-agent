import logging
import json
from typing import List, Dict, Any
from pydantic import BaseModel, ValidationError
from google.cloud import aiplatform
from vertexai.preview.generative_models import GenerativeModel
from .triage_agent import TriagePacket
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class RemediationPlan(BaseModel):
    """
    Represents a detailed plan for remediating an issue, including root cause, proposed fix,
    and code/IaC patches.
    """
    root_cause_analysis: str
    proposed_fix: str
    code_patch: str
    iac_fix: str

class AnalysisAgent:
    """
    A class responsible for performing deep analysis of issues using a Gemini model
    to generate remediation plans.
    """
    def __init__(self, project_id: str, location: str, analysis_model: str):
        """
        Initializes the AnalysisAgent with GCP project, location, and the analysis model to use.

        Args:
            project_id (str): The Google Cloud project ID.
            location (str): The GCP region where the model is hosted (e.g., "us-central1").
            analysis_model (str): The name of the Gemini model to use for analysis.
        """
        self.project_id: str = project_id
        self.location: str = location
        self.analysis_model: str = analysis_model
        aiplatform.init(project=project_id, location=location)
        self.model: GenerativeModel = GenerativeModel(analysis_model)
        logger.info(f"[ANALYSIS] AnalysisAgent initialized with model: {analysis_model} in {location} for project: {project_id}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((RuntimeError, ValueError, json.JSONDecodeError))
    )
    async def analyze_issue( # Changed to async def
        self, triage_packet: TriagePacket, historical_logs: List[str], configs: Dict[str, str]
    ) -> RemediationPlan:
        """
        Analyzes an issue based on a triage packet, historical logs, and configurations
        to generate a RemediationPlan.

        Args:
            triage_packet (TriagePacket): The triage information for the issue.
            historical_logs (List[str]): A list of relevant historical log entries.
            configs (Dict[str, str]): A dictionary of configuration files (e.g., IaC, service configs).

        Returns:
            RemediationPlan: A structured plan for remediating the issue.
        """
        logger.info(f"[ANALYSIS] Analyzing issue: issue_id={triage_packet.issue_id}, historical_logs={len(historical_logs)}, configs={len(configs)}")
        
        # Construct the prompt for the Gemini model
        prompt_template: str = """
        You are an expert SRE Analysis Agent. Your task is to perform a deep root cause analysis of the provided issue,
        considering the triage information, historical logs, and relevant configurations.
        Then, generate a comprehensive remediation plan in structured JSON format.

        The JSON object must conform to the following schema:
        {{
            "root_cause_analysis": "A detailed analysis of the root cause of the issue.",
            "proposed_fix": "A clear description of the proposed fix.",
            "code_patch": "If applicable, a code patch (e.g., Python, Java, Go) to fix the issue. Provide the full code block.",
            "iac_fix": "If applicable, an Infrastructure as Code (IaC) fix (e.g., Terraform, Kubernetes YAML) for the issue. Provide the full code block."
        }}

        Triage Packet:
        {triage_packet_json}

        Historical Logs:
        {historical_logs_str}

        Configurations:
        {configs_str}

        Provide only the JSON response.
        """
        
        prompt: str = prompt_template.format(
            triage_packet_json=triage_packet.model_dump_json(),
            historical_logs_str=json.dumps(historical_logs, indent=2),
            configs_str=json.dumps(configs, indent=2)
        )
        logger.debug(f"[ANALYSIS] Prompt for analysis model: {prompt[:500]}...")

        json_response_str: str = "" # Initialize json_response_str

        try:
            # Call the Gemini model (synchronous)
            response = self.model.generate_content(prompt) # Removed await
            
            # Extract and parse the JSON response
            json_response_str = response.text.strip()
            logger.debug(f"[ANALYSIS] Raw model response: {json_response_str[:500]}...")

            remediation_data: Dict[str, Any] = json.loads(json_response_str)
            remediation_plan: RemediationPlan = RemediationPlan(**remediation_data)
            
            logger.info(f"[ANALYSIS] Analysis complete for issue {triage_packet.issue_id}.")
            return remediation_plan

        except ValidationError as e:
            logger.error(f"[ERROR_HANDLING] Failed to validate RemediationPlan schema from model response: {e}")
            raise ValueError(f"Invalid model response schema: {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"[ERROR_HANDLING] Failed to decode JSON from model response: {e}. Response: {json_response_str}")
            raise ValueError(f"Malformed JSON response from model: {e}") from e
        except Exception as e:
            logger.error(f"[ERROR_HANDLING] Error calling Gemini Analysis model: {e}")
            raise RuntimeError(f"Gemini Analysis model call failed: {e}") from e
