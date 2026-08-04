from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, PlatformSetupInfo, TestInfo, ServiceHint
from app.core.platform_detect import Platform


class NodeDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "javascript"

    @property
    def default_runtime_version(self) -> str:
        return "20"

    @property
    def platform_setups(self) -> dict[Platform, PlatformSetupInfo]:
        return {
            Platform.GITHUB_ACTIONS: PlatformSetupInfo("actions/setup-node@v4", "node-version"),
            Platform.AZURE_PIPELINES: PlatformSetupInfo("NodeTool@0", "versionSpec"),
        }

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
                manifest_file="package.json",
                lockfile="yarn.lock",
                cache_path="$(Pipeline.Workspace)/.yarn/cache",
            ),
            "pnpm-lock.yaml": DependencyInfo(
                manager="pnpm", language="javascript",
                install_command="pnpm install --frozen-lockfile",
                build_command="pnpm build",
                manifest_file="package.json",
                lockfile="pnpm-lock.yaml",
                cache_path="$(Pipeline.Workspace)/.pnpm-store",
            ),
        }

    def resolve_dependency_info(
        self, directory: Path, matched_marker: str, base_info: DependencyInfo,
    ) -> DependencyInfo:
        """Refine install command, lockfile, runner_image, and runner_entrypoint.

        1. Lockfile Verification: Only assign lockfile if it actually exists in directory.
        2. Application Categorization: Distinguish static web frontend (Vite, React, Vue, Svelte)
           which requires NGINX serving, from Node.js backend runtime applications (Express, NestJS).
        """
        install_cmd = base_info.install_command
        manifest = base_info.manifest_file or matched_marker
        lockfile = None
        runner_image = "node:20-slim"
        runner_entrypoint = "npm start"

        pkg_json = directory / "package.json"
        is_static_frontend = False

        if pkg_json.exists():
            try:
                import json
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                scripts = data.get("scripts", {})
                deps = data.get("dependencies", {})
                dev_deps = data.get("devDependencies", {})
                all_deps = {**deps, **dev_deps}

                # Detect static frontend tools (Vite, React Scripts, Vue CLI, Svelte, Astro, Parcel)
                frontend_indicators = {"vite", "react-scripts", "@vue/cli", "astro", "@angular/cli", "svelte", "parcel"}
                backend_indicators = {"express", "nest", "@nestjs/core", "fastify", "koa"}

                has_frontend_tool = any(tool in all_deps for tool in frontend_indicators)
                has_backend_framework = any(tool in all_deps for tool in backend_indicators)

                if has_frontend_tool and not has_backend_framework:
                    is_static_frontend = True

                main_file = data.get("main")
                if "start" in scripts:
                    runner_entrypoint = "npm start"
                elif main_file:
                    runner_entrypoint = f"node {main_file}"
            except Exception:
                pass

        if is_static_frontend:
            app_type = "static_frontend"
            publish_dir = "dist"
            runner_image = "nginx:alpine"
            runner_entrypoint = 'nginx -g "daemon off;"'
        else:
            app_type = "runtime_service"
            publish_dir = None

        # Safely assign lockfile only if it actually exists on disk
        if (directory / "package-lock.json").exists():
            lockfile = "package-lock.json"
            install_cmd = "npm ci"
        elif (directory / "yarn.lock").exists():
            lockfile = "yarn.lock"
            install_cmd = "yarn install --frozen-lockfile"
        elif (directory / "pnpm-lock.yaml").exists():
            lockfile = "pnpm-lock.yaml"
            install_cmd = "pnpm install --frozen-lockfile"
        elif (directory / "npm-shrinkwrap.json").exists():
            lockfile = "npm-shrinkwrap.json"
            install_cmd = "npm ci"
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
            runner_image=runner_image,
            runner_entrypoint=runner_entrypoint,
            app_type=app_type,
            publish_dir=publish_dir,
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

        # 3. If no pinned version found in files/package.json, return None (handled by default_runtime_version)
        return None
