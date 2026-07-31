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
                azure_setup_task="NodeTool@0",
                azure_version_key="versionSpec",
                github_setup_action="actions/setup-node@v4",
                github_version_key="node-version",
            ),
            "yarn.lock": DependencyInfo(
                manager="yarn", language="javascript",
                install_command="yarn install --frozen-lockfile",
                build_command="yarn build",
                manifest_file="package.json",
                lockfile="yarn.lock",
                cache_path="$(Pipeline.Workspace)/.yarn/cache",
                azure_setup_task="NodeTool@0",
                azure_version_key="versionSpec",
                github_setup_action="actions/setup-node@v4",
                github_version_key="node-version",
            ),
            "pnpm-lock.yaml": DependencyInfo(
                manager="pnpm", language="javascript",
                install_command="pnpm install --frozen-lockfile",
                build_command="pnpm build",
                manifest_file="package.json",
                lockfile="pnpm-lock.yaml",
                cache_path="$(Pipeline.Workspace)/.pnpm-store",
                azure_setup_task="NodeTool@0",
                azure_version_key="versionSpec",
                github_setup_action="actions/setup-node@v4",
                github_version_key="node-version",
            ),
        }

    def resolve_dependency_info(
        self, directory: Path, matched_marker: str, base_info: DependencyInfo,
    ) -> DependencyInfo:
        """Refine install command and lockfile based on coexisting files.

        npm ci strictly requires package-lock.json or npm-shrinkwrap.json.
        If no lockfile is committed to the repository, fall back to npm install.
        """
        install_cmd = base_info.install_command
        manifest = base_info.manifest_file or matched_marker
        lockfile = base_info.lockfile

        if matched_marker == "package.json":
            if (directory / "package-lock.json").exists():
                lockfile = "package-lock.json"
            elif (directory / "npm-shrinkwrap.json").exists():
                lockfile = "npm-shrinkwrap.json"
            else:
                lockfile = None
                install_cmd = "npm install"

        return DependencyInfo(
            manager=base_info.manager,
            language=base_info.language,
            install_command=install_cmd,
            build_command=base_info.build_command,
            publish_command=base_info.publish_command,
            manifest_file=manifest,
            lockfile=lockfile,
            working_dir=base_info.working_dir,
            cache_path=base_info.cache_path,
            cache_env_var=base_info.cache_env_var,
            azure_setup_task=base_info.azure_setup_task,
            azure_version_key=base_info.azure_version_key,
            github_setup_action=base_info.github_setup_action,
            github_version_key=base_info.github_version_key,
        )

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

    def detect_runtime_version(self, repo_dir: Path) -> str | None:
        import re

        # 1. Check version files like .nvmrc or .node-version
        result = super().detect_runtime_version(repo_dir)
        if result:
            return result.strip().lstrip("v")

        # 2. Check package.json engines.node configuration
        pkg_json = repo_dir / "package.json"
        if pkg_json.exists():
            try:
                import json
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                node_engine = data.get("engines", {}).get("node")
                if node_engine:
                    match = re.search(r"(\d+(?:\.\d+)*)", node_engine)
                    if match:
                        return match.group(1)
            except Exception:
                pass

        # 3. Fallback to default modern LTS version if no pinned version is specified
        return "20.x"
