from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, TestInfo, ServiceHint


class NodeDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "javascript"

    @property
    def extension_map(self) -> dict[str, str]:
        return {
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
        }

    @property
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        return {
            "package.json": DependencyInfo(
                manager="npm", language="javascript",
                install_command="npm ci", build_command="npm run build",
                manifest_file="package.json",
                cache_path="$(Pipeline.Workspace)/.npm",
                cache_env_var="npm_config_cache",
            ),
            "yarn.lock": DependencyInfo(
                manager="yarn", language="javascript",
                install_command="yarn install --frozen-lockfile",
                build_command="yarn build",
                manifest_file="yarn.lock",
                cache_path="$(Pipeline.Workspace)/.yarn/cache",
            ),
            "pnpm-lock.yaml": DependencyInfo(
                manager="pnpm", language="javascript",
                install_command="pnpm install --frozen-lockfile",
                build_command="pnpm build",
                manifest_file="pnpm-lock.yaml",
                cache_path="$(Pipeline.Workspace)/.pnpm-store",
            ),
        }

    @property
    def test_configs(self) -> dict[str, TestInfo]:
        return {
            "jest.config.js": TestInfo(framework="jest", command="npx jest"),
            "jest.config.ts": TestInfo(framework="jest", command="npx jest"),
            "vitest.config.ts": TestInfo(framework="vitest", command="npx vitest run"),
            "vitest.config.js": TestInfo(framework="vitest", command="npx vitest run"),
        }

    @property
    def service_hints(self) -> list[ServiceHint]:
        return [
            ServiceHint("pg", "postgres"),
            ServiceHint("mysql2", "mysql"),
            ServiceHint("redis", "redis"),
            ServiceHint("ioredis", "redis"),
            ServiceHint("mongodb", "mongodb"),
            ServiceHint("mongoose", "mongodb"),
            ServiceHint("elasticsearch", "elasticsearch"),
            ServiceHint("amqplib", "rabbitmq"),
        ]

    @property
    def dep_files_for_service_scan(self) -> list[str]:
        return ["package.json"]

    @property
    def runtime_version_files(self) -> dict[str, str]:
        return {
            ".nvmrc": "javascript",
            ".node-version": "javascript",
        }

    @property
    def entry_point_patterns(self) -> list[str]:
        return ["index.js", "index.ts", "server.js", "server.ts", "app.js", "app.ts"]

    @property
    def monorepo_markers(self) -> list[str]:
        return ["package.json"]

    def detect_test_framework(self, directory: Path) -> TestInfo | None:
        # Check dedicated config files first
        result = super().detect_test_framework(directory)
        if result:
            return result

        # Fall back to parsing package.json for test script references
        pkg_json = directory / "package.json"
        if pkg_json.exists():
            try:
                content = pkg_json.read_text(encoding="utf-8")
                if '"test"' in content:
                    if "jest" in content:
                        return TestInfo(framework="jest", command="npm test")
                    elif "vitest" in content:
                        return TestInfo(framework="vitest", command="npm test")
                    elif "mocha" in content:
                        return TestInfo(framework="mocha", command="npm test")
                    return TestInfo(framework=None, command="npm test")
            except OSError:
                pass

        return None
