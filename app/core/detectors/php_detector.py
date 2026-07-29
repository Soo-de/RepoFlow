from app.core.detectors.base import BaseDetector, DependencyInfo, TestInfo


class PhpDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "php"

    @property
    def extension_map(self) -> dict[str, str]:
        return {".php": "php"}

    @property
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        return {
            "composer.json": DependencyInfo(
                manager="composer", language="php",
                install_command="composer install",
            ),
        }

    @property
    def test_configs(self) -> dict[str, TestInfo]:
        return {
            "phpunit.xml": TestInfo(framework="phpunit", command="vendor/bin/phpunit"),
        }
