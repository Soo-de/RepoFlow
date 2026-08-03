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
    """Dynamically discover and register all BaseDetector subclasses in app.core.detectors."""
    import importlib
    import pkgutil
    import app.core.detectors as detectors_pkg

    registry = DetectorRegistry()
    for _, module_name, _ in pkgutil.iter_modules(detectors_pkg.__path__):
        if module_name in ("base", "registry"):
            continue
        mod = importlib.import_module(f"app.core.detectors.{module_name}")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseDetector) and attr is not BaseDetector:
                # Avoid duplicate registration if imported multiple times
                if not any(isinstance(existing, attr) for existing in registry.detectors):
                    registry.register(attr())
    return registry


default_registry = _build_default_registry()
