# gemini_sre_agent/ml/code_generator_factory.py


from .base_code_generator import BaseCodeGenerator
from .prompt_context_models import IssueType


class CodeGeneratorFactory:
    """Factory for creating specialized code generators"""

    def __init__(self) -> None:
        self.generators: dict[IssueType, BaseCodeGenerator] = {}
        self._initialize_generators()

    def _initialize_generators(self):
        """Initialize all available generators"""
        # Import generators here to avoid circular imports
        try:
            from .specialized_generators.api_generator import APICodeGenerator
            from .specialized_generators.database_generator import DatabaseCodeGenerator
            from .specialized_generators.security_generator import SecurityCodeGenerator

            self.generators = {
                IssueType.DATABASE_ERROR: DatabaseCodeGenerator(),
                IssueType.API_ERROR: APICodeGenerator(),
                IssueType.SECURITY_ERROR: SecurityCodeGenerator(),
            }

            # For now, use placeholders for missing generators
            self._create_placeholder_generators_for_missing_types()

        except ImportError:
            # If specialized generators aren't available yet, use placeholders
            self._create_placeholder_generators()

    def _create_placeholder_generators_for_missing_types(self):
        """Create placeholder generators for missing specialized types"""
        from .base_code_generator import BaseCodeGenerator

        class PlaceholderGenerator(BaseCodeGenerator):
            def _get_domain(self) -> str:
                return "general"

            def _get_generator_type(self) -> str:
                return "placeholder_generator"

            def _load_domain_specific_patterns(self):
                pass

            def _load_domain_specific_rules(self):
                pass

        # Create placeholder generators for missing issue types
        missing_types = [
            IssueType.PERFORMANCE_ERROR,
            IssueType.CONFIGURATION_ERROR,
            IssueType.SERVICE_ERROR,
        ]

        for issue_type in missing_types:
            if issue_type not in self.generators:
                self.generators[issue_type] = PlaceholderGenerator()

    def _create_placeholder_generators(self):
        """Create placeholder generators when specialized ones aren't available"""
        from .base_code_generator import BaseCodeGenerator

        class PlaceholderGenerator(BaseCodeGenerator):
            def _get_domain(self) -> str:
                return "general"

            def _get_generator_type(self) -> str:
                return "placeholder_generator"

            def _load_domain_specific_patterns(self):
                pass

            def _load_domain_specific_rules(self):
                pass

        # Create placeholder generators for each issue type
        for issue_type in IssueType:
            if issue_type != IssueType.UNKNOWN:
                self.generators[issue_type] = PlaceholderGenerator()

    def create_generator(self, issue_type: IssueType) -> BaseCodeGenerator:
        """Create appropriate generator for the given issue type"""
        generator = self.generators.get(issue_type)

        if not generator:
            # Fallback to a general generator
            from .base_code_generator import BaseCodeGenerator

            class GeneralGenerator(BaseCodeGenerator):
                def _get_domain(self) -> str:
                    return "general"

                def _get_generator_type(self) -> str:
                    return "general_generator"

                def _load_domain_specific_patterns(self):
                    pass

                def _load_domain_specific_rules(self):
                    pass

            generator = GeneralGenerator()

        return generator

    def get_supported_issue_types(self) -> list[IssueType]:
        """Get list of supported issue types"""
        return list(self.generators.keys())

    def is_issue_type_supported(self, issue_type: IssueType) -> bool:
        """Check if an issue type is supported"""
        return issue_type in self.generators

    def get_generator_info(self, issue_type: IssueType) -> dict | None:
        """Get information about a specific generator"""
        generator = self.generators.get(issue_type)
        if generator:
            return generator.get_generator_info()
        return None

    def get_all_generators_info(self) -> dict[IssueType, dict]:
        """Get information about all generators"""
        return {
            issue_type: generator.get_generator_info()
            for issue_type, generator in self.generators.items()
        }

    def register_generator(
        self, issue_type: IssueType, generator: BaseCodeGenerator
    ) -> None:
        """Register a new generator for an issue type"""
        self.generators[issue_type] = generator

    def unregister_generator(self, issue_type: IssueType) -> bool:
        """Unregister a generator for an issue type"""
        if issue_type in self.generators:
            del self.generators[issue_type]
            return True
        return False

    def get_generator_count(self) -> int:
        """Get the total number of registered generators"""
        return len(self.generators)

    def get_generator_domains(self) -> list[str]:
        """Get list of all generator domains"""
        domains = set()
        for generator in self.generators.values():
            domains.add(generator._get_domain())
        return list(domains)

    def validate_generators(self) -> dict[str, list[str]]:
        """Validate all generators and return any issues found"""
        issues = {"errors": [], "warnings": []}

        for issue_type, generator in self.generators.items():
            try:
                # Test basic generator functionality
                info = generator.get_generator_info()
                if not info.get("generator_id"):
                    issues["warnings"].append(
                        f"Generator for {issue_type.value} missing generator_id"
                    )

                if not info.get("domain"):
                    issues["warnings"].append(
                        f"Generator for {issue_type.value} missing domain"
                    )

            except Exception as e:
                issues["errors"].append(
                    f"Generator for {issue_type.value} failed validation: {e!s}"
                )

        return issues
