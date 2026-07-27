from app.core.detectors.base import BaseDetector, DependencyInfo, TestInfo


class RubyDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "ruby"

    @property
    def extension_map(self) -> dict[str, str]:
        return {".rb": "ruby"}

    @property
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        return {
            "Gemfile": DependencyInfo(
                manager="bundler", language="ruby",
                install_command="bundle install",
            ),
        }

    @property
    def test_configs(self) -> dict[str, TestInfo]:
        return {
            ".rspec": TestInfo(framework="rspec", command="bundle exec rspec"),
        }

    @property
    def runtime_version_files(self) -> dict[str, str]:
        return {".ruby-version": "ruby"}
