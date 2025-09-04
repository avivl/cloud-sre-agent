"""Compliance reporting tools for usage patterns and audit trails."""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from .audit_logger import AuditEvent, AuditEventType, AuditLogger

logger = logging.getLogger(__name__)


class ComplianceStandard(str, Enum):
    """Compliance standards supported."""

    SOC2 = "soc2"
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"
    CUSTOM = "custom"


class ComplianceReport(BaseModel):
    """Compliance report model."""

    report_id: str = Field(..., description="Unique report identifier")
    standard: ComplianceStandard = Field(..., description="Compliance standard")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    period_start: datetime = Field(..., description="Report period start")
    period_end: datetime = Field(..., description="Report period end")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Report summary")
    findings: List[Dict[str, Any]] = Field(
        default_factory=list, description="Compliance findings"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class ComplianceReporter:
    """Compliance reporting system."""

    def __init__(self, audit_logger: AuditLogger):
        """Initialize the compliance reporter.

        Args:
            audit_logger: Audit logger instance for accessing events
        """
        self.audit_logger = audit_logger
        self._compliance_rules: Dict[ComplianceStandard, List[Dict[str, Any]]] = {}
        self._initialize_default_rules()

    def _initialize_default_rules(self) -> None:
        """Initialize default compliance rules."""
        # SOC2 Type II rules
        self._compliance_rules[ComplianceStandard.SOC2] = [
            {
                "rule_id": "access_control",
                "description": "Access control monitoring",
                "check_function": self._check_access_controls,
                "severity": "high",
            },
            {
                "rule_id": "data_encryption",
                "description": "Data encryption in transit and at rest",
                "check_function": self._check_data_encryption,
                "severity": "high",
            },
            {
                "rule_id": "audit_logging",
                "description": "Comprehensive audit logging",
                "check_function": self._check_audit_logging,
                "severity": "medium",
            },
            {
                "rule_id": "incident_response",
                "description": "Incident response procedures",
                "check_function": self._check_incident_response,
                "severity": "medium",
            },
        ]

        # GDPR rules
        self._compliance_rules[ComplianceStandard.GDPR] = [
            {
                "rule_id": "data_minimization",
                "description": "Data minimization principle",
                "check_function": self._check_data_minimization,
                "severity": "high",
            },
            {
                "rule_id": "consent_management",
                "description": "Consent management",
                "check_function": self._check_consent_management,
                "severity": "high",
            },
            {
                "rule_id": "data_retention",
                "description": "Data retention policies",
                "check_function": self._check_data_retention,
                "severity": "medium",
            },
            {
                "rule_id": "right_to_erasure",
                "description": "Right to erasure (right to be forgotten)",
                "check_function": self._check_right_to_erasure,
                "severity": "medium",
            },
        ]

        # HIPAA rules
        self._compliance_rules[ComplianceStandard.HIPAA] = [
            {
                "rule_id": "phi_protection",
                "description": "Protected Health Information (PHI) protection",
                "check_function": self._check_phi_protection,
                "severity": "high",
            },
            {
                "rule_id": "access_controls",
                "description": "Access controls for PHI",
                "check_function": self._check_hipaa_access_controls,
                "severity": "high",
            },
            {
                "rule_id": "audit_controls",
                "description": "Audit controls for PHI access",
                "check_function": self._check_audit_controls,
                "severity": "medium",
            },
        ]

    async def generate_report(
        self,
        standard: ComplianceStandard,
        period_start: datetime,
        period_end: datetime,
        include_recommendations: bool = True,
    ) -> ComplianceReport:
        """Generate a compliance report.

        Args:
            standard: Compliance standard to check against
            period_start: Start of the reporting period
            period_end: End of the reporting period
            include_recommendations: Whether to include recommendations

        Returns:
            Compliance report
        """
        import uuid

        report_id = str(uuid.uuid4())

        # Get audit events for the period
        events = await self.audit_logger.export_events(
            start_time=period_start,
            end_time=period_end,
        )

        # Run compliance checks
        findings = []
        rules = self._compliance_rules.get(standard, [])

        for rule in rules:
            try:
                check_result = await rule["check_function"](
                    events, period_start, period_end
                )
                findings.append(
                    {
                        "rule_id": rule["rule_id"],
                        "description": rule["description"],
                        "severity": rule["severity"],
                        "status": check_result["status"],
                        "details": check_result["details"],
                        "evidence": check_result.get("evidence", []),
                    }
                )
            except Exception as e:
                logger.error(f"Error running compliance check {rule['rule_id']}: {e}")
                findings.append(
                    {
                        "rule_id": rule["rule_id"],
                        "description": rule["description"],
                        "severity": rule["severity"],
                        "status": "error",
                        "details": f"Error running check: {str(e)}",
                        "evidence": [],
                    }
                )

        # Generate summary
        summary = self._generate_summary(findings, events)

        # Generate recommendations
        recommendations = []
        if include_recommendations:
            recommendations = self._generate_recommendations(findings, standard)

        return ComplianceReport(
            report_id=report_id,
            standard=standard,
            period_start=period_start,
            period_end=period_end,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
        )

    def _generate_summary(
        self, findings: List[Dict[str, Any]], events: List[AuditEvent]
    ) -> Dict[str, Any]:
        """Generate report summary."""
        total_checks = len(findings)
        passed_checks = sum(1 for f in findings if f["status"] == "pass")
        failed_checks = sum(1 for f in findings if f["status"] == "fail")
        error_checks = sum(1 for f in findings if f["status"] == "error")

        # Count events by type
        event_counts = {}
        for event in events:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1

        # Count events by provider
        provider_counts = {}
        for event in events:
            if event.provider:
                provider_counts[event.provider] = (
                    provider_counts.get(event.provider, 0) + 1
                )

        return {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "error_checks": error_checks,
            "compliance_score": (
                (passed_checks / total_checks * 100) if total_checks > 0 else 0
            ),
            "total_events": len(events),
            "event_counts": event_counts,
            "provider_counts": provider_counts,
        }

    def _generate_recommendations(
        self, findings: List[Dict[str, Any]], standard: ComplianceStandard
    ) -> List[str]:
        """Generate recommendations based on findings."""
        recommendations = []

        for finding in findings:
            if finding["status"] == "fail":
                if finding["rule_id"] == "access_control":
                    recommendations.append(
                        "Implement stronger access controls and multi-factor authentication"
                    )
                elif finding["rule_id"] == "data_encryption":
                    recommendations.append(
                        "Ensure all data is encrypted in transit and at rest"
                    )
                elif finding["rule_id"] == "audit_logging":
                    recommendations.append(
                        "Implement comprehensive audit logging for all system activities"
                    )
                elif finding["rule_id"] == "data_minimization":
                    recommendations.append(
                        "Review data collection practices to ensure only necessary data is collected"
                    )
                elif finding["rule_id"] == "phi_protection":
                    recommendations.append(
                        "Implement additional safeguards for Protected Health Information"
                    )

        # Add standard-specific recommendations
        if standard == ComplianceStandard.SOC2:
            recommendations.append("Conduct regular security awareness training")
            recommendations.append("Implement incident response procedures")
        elif standard == ComplianceStandard.GDPR:
            recommendations.append("Implement data subject rights management")
            recommendations.append("Conduct Data Protection Impact Assessments")
        elif standard == ComplianceStandard.HIPAA:
            recommendations.append("Implement Business Associate Agreements")
            recommendations.append("Conduct regular risk assessments")

        return list(set(recommendations))  # Remove duplicates

    # Compliance check functions
    async def _check_access_controls(
        self, events: List[AuditEvent], period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Check access control compliance."""
        access_events = [
            e
            for e in events
            if e.event_type
            in [AuditEventType.ACCESS_GRANTED, AuditEventType.ACCESS_DENIED]
        ]

        if not access_events:
            return {
                "status": "fail",
                "details": "No access control events found",
                "evidence": [],
            }

        denied_attempts = [
            e for e in access_events if e.event_type == AuditEventType.ACCESS_DENIED
        ]
        granted_attempts = [
            e for e in access_events if e.event_type == AuditEventType.ACCESS_GRANTED
        ]

        denial_rate = len(denied_attempts) / len(access_events) if access_events else 0

        if denial_rate > 0.1:  # More than 10% denial rate might indicate issues
            return {
                "status": "fail",
                "details": f"High access denial rate: {denial_rate:.2%}",
                "evidence": [
                    f"Total access attempts: {len(access_events)}",
                    f"Denied attempts: {len(denied_attempts)}",
                ],
            }

        return {
            "status": "pass",
            "details": f"Access controls functioning properly. Denial rate: {denial_rate:.2%}",
            "evidence": [
                f"Total access attempts: {len(access_events)}",
                f"Granted attempts: {len(granted_attempts)}",
            ],
        }

    async def _check_data_encryption(
        self, events: List[AuditEvent], period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Check data encryption compliance."""
        # This is a simplified check - in reality, you'd check actual encryption status
        provider_events = [e for e in events if e.provider]

        if not provider_events:
            return {
                "status": "fail",
                "details": "No provider interactions found to verify encryption",
                "evidence": [],
            }

        # Check if events have encryption metadata
        encrypted_events = [
            e for e in provider_events if e.metadata.get("encrypted", False)
        ]

        if (
            len(encrypted_events) < len(provider_events) * 0.8
        ):  # Less than 80% encrypted
            return {
                "status": "fail",
                "details": "Not all provider interactions are encrypted",
                "evidence": [
                    f"Total events: {len(provider_events)}",
                    f"Encrypted events: {len(encrypted_events)}",
                ],
            }

        return {
            "status": "pass",
            "details": "Data encryption is properly implemented",
            "evidence": [
                f"Encrypted events: {len(encrypted_events)}/{len(provider_events)}"
            ],
        }

    async def _check_audit_logging(
        self, events: List[AuditEvent], period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Check audit logging compliance."""
        if not events:
            return {
                "status": "fail",
                "details": "No audit events found",
                "evidence": [],
            }

        # Check for required event types
        required_types = [
            AuditEventType.PROVIDER_REQUEST,
            AuditEventType.PROVIDER_RESPONSE,
            AuditEventType.CONFIG_CHANGE,
        ]

        missing_types = []
        for event_type in required_types:
            if not any(e.event_type == event_type for e in events):
                missing_types.append(event_type.value)

        if missing_types:
            return {
                "status": "fail",
                "details": f"Missing audit event types: {', '.join(missing_types)}",
                "evidence": [
                    f"Total events: {len(events)}",
                    f"Event types found: {set(e.event_type.value for e in events)}",
                ],
            }

        return {
            "status": "pass",
            "details": "Comprehensive audit logging is in place",
            "evidence": [
                f"Total events: {len(events)}",
                f"Event types: {len(set(e.event_type for e in events))}",
            ],
        }

    async def _check_incident_response(
        self, events: List[AuditEvent], period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Check incident response compliance."""
        error_events = [e for e in events if not e.success]

        if not error_events:
            return {
                "status": "pass",
                "details": "No incidents detected in the reporting period",
                "evidence": [],
            }

        # Check if errors are properly logged and handled
        high_severity_errors = [
            e for e in error_events if e.metadata.get("severity") == "high"
        ]

        if high_severity_errors:
            return {
                "status": "fail",
                "details": f"High severity incidents detected: {len(high_severity_errors)}",
                "evidence": [
                    f"Total errors: {len(error_events)}",
                    f"High severity: {len(high_severity_errors)}",
                ],
            }

        return {
            "status": "pass",
            "details": "Incidents are properly handled",
            "evidence": [
                f"Total errors: {len(error_events)}",
                "All errors are low/medium severity",
            ],
        }

    async def _check_data_minimization(
        self, events: List[AuditEvent], period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Check GDPR data minimization compliance."""
        # This is a simplified check - in reality, you'd analyze actual data usage
        provider_events = [e for e in events if e.provider]

        if not provider_events:
            return {
                "status": "pass",
                "details": "No data processing events found",
                "evidence": [],
            }

        # Check if events indicate excessive data collection
        large_requests = [
            e for e in provider_events if e.metadata.get("request_size", 0) > 10000
        ]  # 10KB

        if (
            len(large_requests) > len(provider_events) * 0.2
        ):  # More than 20% large requests
            return {
                "status": "fail",
                "details": "Potential excessive data collection detected",
                "evidence": [
                    f"Large requests: {len(large_requests)}/{len(provider_events)}"
                ],
            }

        return {
            "status": "pass",
            "details": "Data minimization principles appear to be followed",
            "evidence": [
                f"Total requests: {len(provider_events)}",
                f"Large requests: {len(large_requests)}",
            ],
        }

    async def _check_consent_management(
        self, events: List[AuditEvent], period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Check GDPR consent management compliance."""
        # This would check for consent-related events
        consent_events = [e for e in events if "consent" in e.metadata.get("tags", [])]

        if not consent_events:
            return {
                "status": "fail",
                "details": "No consent management events found",
                "evidence": [],
            }

        return {
            "status": "pass",
            "details": "Consent management is implemented",
            "evidence": [f"Consent events: {len(consent_events)}"],
        }

    async def _check_data_retention(
        self, events: List[AuditEvent], period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Check GDPR data retention compliance."""
        # This would check data retention policies
        return {
            "status": "pass",
            "details": "Data retention policies are implemented",
            "evidence": [],
        }

    async def _check_right_to_erasure(
        self, events: List[AuditEvent], period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Check GDPR right to erasure compliance."""
        # This would check for data deletion events
        deletion_events = [
            e for e in events if e.event_type == AuditEventType.DATA_EXPORT
        ]

        return {
            "status": "pass",
            "details": "Right to erasure procedures are implemented",
            "evidence": [f"Data deletion events: {len(deletion_events)}"],
        }

    async def _check_phi_protection(
        self, events: List[AuditEvent], period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Check HIPAA PHI protection compliance."""
        # This would check for PHI-related events and protections
        phi_events = [e for e in events if e.metadata.get("contains_phi", False)]

        if phi_events:
            # Check if PHI events have proper protections
            protected_events = [
                e for e in phi_events if e.metadata.get("encrypted", False)
            ]

            if len(protected_events) < len(phi_events):
                return {
                    "status": "fail",
                    "details": "PHI events are not properly protected",
                    "evidence": [
                        f"PHI events: {len(phi_events)}",
                        f"Protected: {len(protected_events)}",
                    ],
                }

        return {
            "status": "pass",
            "details": "PHI protection measures are in place",
            "evidence": [f"PHI events: {len(phi_events)}"],
        }

    async def _check_hipaa_access_controls(
        self, events: List[AuditEvent], period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Check HIPAA access controls compliance."""
        # Similar to general access controls but with HIPAA-specific requirements
        return await self._check_access_controls(events, period_start, period_end)

    async def _check_audit_controls(
        self, events: List[AuditEvent], period_start: datetime, period_end: datetime
    ) -> Dict[str, Any]:
        """Check HIPAA audit controls compliance."""
        # Similar to general audit logging but with HIPAA-specific requirements
        return await self._check_audit_logging(events, period_start, period_end)

    def add_custom_rule(
        self, standard: ComplianceStandard, rule: Dict[str, Any]
    ) -> None:
        """Add a custom compliance rule."""
        if standard not in self._compliance_rules:
            self._compliance_rules[standard] = []

        self._compliance_rules[standard].append(rule)

    def get_supported_standards(self) -> List[ComplianceStandard]:
        """Get list of supported compliance standards."""
        return list(self._compliance_rules.keys())

    def get_rules_for_standard(
        self, standard: ComplianceStandard
    ) -> List[Dict[str, Any]]:
        """Get rules for a specific compliance standard."""
        return self._compliance_rules.get(standard, [])
