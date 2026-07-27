from app.core.detectors.base import BaseDetector


class DetectorRegistry:
    """Central registry that holds all ecosystem detectors.

    Provides aggregate lookup methods used by repo_analysis to query
    across all registered ecosystems without knowing individual plugins.
    """

    def __init__(self) -> None:
        self._detectors: list[BaseDetector] = []
        self._extension_map: dict[str, str] = {}

    def register(self, detector: BaseDetector) -> None:
        """Register a detector and index its file extensions."""
        self._detectors.append(detector)
        self._extension_map.update(detector.extension_map)

    @property
    def detectors(self) -> list[BaseDetector]:
        return list(self._detectors)

    @property
    def extension_map(self) -> dict[str, str]:
        """Aggregated mapping of file extensions to language names."""
        return dict(self._extension_map)

    def all_entry_point_patterns(self) -> list[str]:
        """Collect entry point patterns from every registered detector."""
        patterns: list[str] = []
        for detector in self._detectors:
            patterns.extend(detector.entry_point_patterns)
        return patterns

    def all_monorepo_markers(self) -> set[str]:
        """Collect monorepo marker filenames from every registered detector."""
        markers: set[str] = set()
        for detector in self._detectors:
            markers.update(detector.monorepo_markers)
        return markers


def _build_default_registry() -> DetectorRegistry:
    """Construct and populate the registry with all built-in detectors."""
    from app.core.detectors.python_detector import PythonDetector
    from app.core.detectors.node_detector import NodeDetector
    from app.core.detectors.go_detector import GoDetector
    from app.core.detectors.rust_detector import RustDetector
    from app.core.detectors.java_detector import JavaDetector
    from app.core.detectors.c_detector import CDetector
    from app.core.detectors.ruby_detector import RubyDetector
    from app.core.detectors.php_detector import PhpDetector
    from app.core.detectors.swift_detector import SwiftDetector
    from app.core.detectors.kotlin_detector import KotlinDetector
    from app.core.detectors.csharp_detector import CSharpDetector

    registry = DetectorRegistry()
    registry.register(PythonDetector())
    registry.register(NodeDetector())
    registry.register(GoDetector())
    registry.register(RustDetector())
    registry.register(JavaDetector())
    registry.register(CDetector())
    registry.register(RubyDetector())
    registry.register(PhpDetector())
    registry.register(SwiftDetector())
    registry.register(KotlinDetector())
    registry.register(CSharpDetector())
    return registry


default_registry = _build_default_registry()
