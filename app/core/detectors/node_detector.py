from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, EnvironmentRequirement, PlatformSetupInfo, TestInfo, ServiceHint
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
        """Refine install command, lockfile, runner_image, runner_entrypoint,
        environment requirements, and build output path.

        1. Lockfile Verification: Only assign lockfile if it actually exists in directory.
        2. Application Categorization: Distinguish static web frontend from Node.js backend.
        3. Compatibility Detection: Detect legacy OpenSSL requirement for old build tools on Node 17+.
        4. Build Output Resolution: Resolve actual build artifact path (e.g. Angular's dist/<app>/browser).
        """
        import json
        import re

        install_cmd = base_info.install_command
        manifest = base_info.manifest_file or matched_marker
        lockfile = None
        runner_image = "node:20-slim"
        runner_entrypoint = "npm start"
        environment_reqs: list[EnvironmentRequirement] = []
        build_output_path: str | None = None

        pkg_json = directory / "package.json"
        is_static_frontend = False

        if pkg_json.exists():
            try:
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

                # --- Compatibility detection: legacy OpenSSL for old build tools ---
                environment_reqs.extend(
                    self._detect_openssl_requirement(all_deps, directory)
                )

                # --- Build output resolution for Angular projects ---
                if (directory / "angular.json").exists() or any(dep.startswith("@angular/") for dep in all_deps):
                    build_output_path = self._resolve_angular_output_path(directory)

            except Exception:
                pass

        if is_static_frontend:
            app_type = "static_frontend"
            publish_dir = build_output_path or "dist"
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
            environment_requirements=environment_reqs,
            build_output_path=build_output_path,
            cache_key_files=[lockfile] if lockfile else [manifest],
        )

    def _detect_openssl_requirement(
        self, all_deps: dict[str, str], directory: Path,
    ) -> list[EnvironmentRequirement]:
        """Detect whether old Webpack-based build tools need --openssl-legacy-provider.

        Returns an EnvironmentRequirement when a legacy build tool version is found
        and the resolved Node runtime is 17+. The requirement is expressed generically
        so the pipeline renderer can place it appropriately for any CI/CD platform.
        """
        import re

        legacy_tool_patterns = {
            "webpack": 4,
            "@angular/cli": 15,
            "react-scripts": 4,
        }

        needs_legacy = False
        for tool, max_legacy_major in legacy_tool_patterns.items():
            version_spec = all_deps.get(tool)
            if not version_spec:
                continue
            match = re.search(r"(\d+)", version_spec)
            if match and int(match.group(1)) <= max_legacy_major:
                needs_legacy = True
                break

        if not needs_legacy:
            return []

        # Check whether the resolved runtime is Node 17+
        node_version = self.detect_runtime_version(directory)
        if node_version is None:
            node_version = self.default_runtime_version

        try:
            major = int(node_version.split(".")[0])
        except (ValueError, AttributeError):
            return []

        if major < 17:
            return []

        return [
            EnvironmentRequirement(
                kind="env_var",
                key="NODE_OPTIONS",
                value="--openssl-legacy-provider",
                reason=(
                    "Legacy build tool requires OpenSSL legacy provider on Node.js 17+ "
                    "to avoid ERR_OSSL_EVP_UNSUPPORTED"
                ),
            ),
        ]

    def _resolve_angular_output_path(self, directory: Path) -> str | None:
        """Parse angular.json to determine the actual build output path.

        Angular CLI writes build artifacts to a path defined in angular.json's
        architect.build.options.outputPath. The structure depends on the builder:

        - ``@angular-devkit/build-angular:application`` or ``@angular/build:application`` (Angular 17+)
          outputs to ``<outputPath>/browser/``.
        - ``@angular-devkit/build-angular:browser`` (legacy)
          outputs directly to ``<outputPath>/``.

        An object-typed outputPath (``{"base": "..."}``) is also an Angular 17+ signal
        that implies the ``browser/`` subdirectory.
        """
        import json

        angular_json = directory / "angular.json"
        if not angular_json.exists():
            candidates = list(directory.rglob("angular.json"))
            if candidates:
                angular_json = candidates[0]
            else:
                return None

        try:
            config = json.loads(angular_json.read_text(encoding="utf-8"))
            projects = config.get("projects", {})
            default_project = config.get("defaultProject")

            target_project = None
            project_name = None

            # 1. Try defaultProject if specified
            if default_project and default_project in projects and isinstance(projects[default_project], dict):
                target_project = projects[default_project]
                project_name = default_project

            # 2. Otherwise find the first project with projectType == "application" or a build architect target
            if not target_project:
                for p_name, p_val in projects.items():
                    if isinstance(p_val, dict):
                        p_type = p_val.get("projectType")
                        architect = p_val.get("architect", {})
                        if p_type == "application" or "build" in architect:
                            target_project = p_val
                            project_name = p_name
                            break

            # 3. Fallback: pick any project dict if available
            if not target_project:
                for p_name, p_val in projects.items():
                    if isinstance(p_val, dict):
                        target_project = p_val
                        project_name = p_name
                        break

            if not target_project or not isinstance(target_project, dict):
                return None

            build_config = target_project.get("architect", {}).get("build", {})
            builder = build_config.get("builder", "")
            output_path = build_config.get("options", {}).get("outputPath")

            if output_path is None:
                base_path = f"dist/{project_name}" if project_name else "dist"
            elif isinstance(output_path, dict):
                base_path = output_path.get("base", f"dist/{project_name}")
            else:
                base_path = str(output_path)

            uses_application_builder = (
                isinstance(output_path, dict)
                or "application" in builder
                or "app-shell" in builder
            )

            if uses_application_builder:
                return f"{base_path}/browser"

            return base_path

        except Exception:
            return None

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

        # 3. Check for postcss subpath exports incompatibility requiring Node ≤16
        compat_version = self._detect_postcss_compat_version(repo_dir)
        if compat_version:
            return compat_version

        return None

    def _detect_postcss_compat_version(self, repo_dir: Path) -> str | None:
        """Detect old build tools that need Node ≤16 due to postcss subpath exports.

        Node 17+ enforces strict "exports" in package.json. Old versions of
        css-loader, postcss-loader, and Angular CLI internally call
        require('postcss/package.json') which is not exposed in postcss v8+'s
        exports map, causing ERR_PACKAGE_PATH_NOT_EXPORTED at build time.

        Returning "16" here caps the Node version before the default (20) kicks in,
        which also avoids the OpenSSL 3.0 issue on these same old projects.
        """
        import json
        import re

        pkg_json = repo_dir / "package.json"
        if not pkg_json.exists():
            return None

        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
        except Exception:
            return None

        deps = data.get("dependencies", {})
        dev_deps = data.get("devDependencies", {})
        all_deps = {**deps, **dev_deps}

        # Packages and their max major versions that trigger the incompatibility
        compat_thresholds = {
            "@angular/cli": 12,
            "@angular/core": 12,
            "postcss-loader": 4,
            "css-loader": 5,
            "@vue/cli-service": 4,
        }

        for pkg, max_compat_major in compat_thresholds.items():
            version_spec = all_deps.get(pkg)
            if not version_spec:
                continue
            match = re.search(r"(\d+)", version_spec)
            if match and int(match.group(1)) <= max_compat_major:
                return "16"

        return None
