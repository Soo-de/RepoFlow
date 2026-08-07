from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, PlatformSetupInfo, TestInfo
from app.core.platform_detect import Platform


class PhpDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "php"

    @property
    def platform_setups(self) -> dict[Platform, PlatformSetupInfo]:
        return {
            Platform.GITHUB_ACTIONS: PlatformSetupInfo("shivammathur/setup-php@v2", "php-version"),
            Platform.AZURE_PIPELINES: PlatformSetupInfo("UsePhpVersion@0", "versionSpec"),
        }

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
