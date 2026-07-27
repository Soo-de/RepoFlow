from app.core.detectors.base import BaseDetector, DependencyInfo


class CSharpDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "csharp"

    @property
    def extension_map(self) -> dict[str, str]:
        return {".cs": "csharp"}

    @property
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        return {}

    @property
    def entry_point_patterns(self) -> list[str]:
        return ["Program.cs"]
