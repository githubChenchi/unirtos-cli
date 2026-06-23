#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unirtos Build Module
Core Functionality:
    - Resolve installed SDK path from env_config.json
    - Delegate build entry to SDK root build.sh (SDK-driven build flow)
    - Inject external app directory so SDK can compile user app outside SDK tree
Copyright (c) Chavis.Chen 2026. All Rights Reserved.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import json
from unirtos_cli import unirtos_env_setup as env

# ===================== Command Line Argument Parser =====================
def parse_build_args() -> argparse.Namespace:
    """
    Parse command line arguments for build module.
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Unirtos Project Build Module",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-b", "--build-dir",
        default="build",
        help="Reserved compatibility option (unused in SDK-driven build mode)"
    )
    parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=None,
        help="Number of parallel build jobs (overrides env_config.json build.jobs)"
    )
    parser.add_argument(
        "-m", "--module",
        default=None,
        help="SDK module/project name, e.g., EG800ZCN_LA (overrides env_config.json build.module)"
    )
    parser.add_argument(
        "--version",
        default=None,
        help="SDK build version string (overrides env_config.json build.version)"
    )
    return parser.parse_args()

# ===================== Configuration Loader =====================
def load_unirtos_config() -> dict:
    """
    Load and validate environment configuration from env_config.json (fixed path).
    Ensures configuration consistency with unirtos_env_setup module.
    
    Returns:
        dict: Parsed Unirtos environment configuration
    
    Raises:
        RuntimeError: If config file is missing or has invalid JSON syntax
    """
    config_path = Path("env_config.json").absolute()

    # Validate config file existence
    if not config_path.exists():
        raise RuntimeError(
            f"ERROR: Configuration file not found: {config_path}\n"
            "Resolution Steps:\n"
            "1. Confirm env_config.json exists in the build script directory\n"
            "2. Generate a valid config file with 'unirtos-cli init'"
        )

    # Load config using env_setup's interface for consistency
    try:
        return env.load_config(str(config_path))
    except json.JSONDecodeError:
        raise RuntimeError(
            f"ERROR: Invalid JSON syntax in {config_path}\n"
            "Resolution Steps:\n"
            "1. Check for syntax errors (e.g., missing commas/quotes)\n"
            "2. Regenerate config file with 'unirtos-cli init' if necessary"
        )
    except Exception as e:
        raise RuntimeError(f"Configuration load failed: {str(e)}")

def resolve_sdk_path(config: dict) -> Path:
    """Resolve installed SDK path without pulling; env-setup owns sync/pull."""
    unirtos_root = env.get_unirtos_root(config)
    sdk_version = config["sdk"]["version"]
    sdk_path = unirtos_root / "sdk" / f"v{sdk_version}"

    print("\n===== Unirtos Version Configuration =====")
    print(f"SDK Version: {sdk_version}")
    print("=========================================\n")
    print(f"INFO: Unirtos root directory: {unirtos_root}")

    if not sdk_path.exists():
        raise RuntimeError(
            f"SDK v{sdk_version} not found at: {sdk_path}\n"
            "Please run 'unirtos-cli env-setup' first to pull and prepare SDK."
        )

    print(f"INFO: SDK v{sdk_version} path: {sdk_path}")
    return sdk_path


def resolve_sdk_build_profile(config: dict, args: argparse.Namespace, app_root: Path) -> dict:
    """Resolve SDK build.sh make profile from env_config.json and CLI overrides."""
    build_cfg = config.get("build", {})
    if not isinstance(build_cfg, dict):
        build_cfg = {}

    module = args.module or build_cfg.get("module")
    # Default target/version uses the app root folder name (where env_config.json is located).
    version = args.version or build_cfg.get("version") or app_root.name

    jobs_from_config = build_cfg.get("jobs", 4)
    jobs = args.jobs if args.jobs is not None else jobs_from_config

    if not module:
        raise RuntimeError(
            "Missing SDK build profile. Configure 'build.module' in env_config.json, "
            "or pass --module."
        )

    try:
        jobs = int(jobs)
        if jobs <= 0:
            raise ValueError()
    except Exception:
        raise RuntimeError("Invalid jobs value, expected a positive integer.")

    # Fixed for external app mode: type=app (output stays in app dir), operation=r (incremental)
    return {
        "project": module,
        "version": version,
        "type": "app",
        "operation": "r",
        "jobs": jobs,
    }


def run_sdk_build(config: dict, args: argparse.Namespace) -> None:
    """
    Build entry: invoke SDK root build.sh and let SDK CMake pull in external app.

    External app directory is injected via UNIRTOS_EXTERNAL_APP_DIR.
    """
    app_root = Path(os.getcwd()).absolute()
    app_cmake = app_root / "CMakeLists.txt"
    if not app_cmake.exists():
        raise RuntimeError(
            f"App CMakeLists.txt not found: {app_cmake}\n"
            "Run 'unirtos-cli init' first or ensure this is a valid external app project directory."
        )

    sdk_path = resolve_sdk_path(config)
    build_profile = resolve_sdk_build_profile(config, args, app_root)

    # unirtos is the global command provided by the cross-compilation toolchain.
    # It must be executed from the SDK root directory.
    import shutil
    if not shutil.which("unirtos"):
        raise RuntimeError(
            "Global 'unirtos' command not found in PATH.\n"
            "Ensure the UniRTOS cross-compilation toolchain is installed and added to PATH."
        )

    cmd = [
        "unirtos",
        "make",
        "--project",
        build_profile["project"],
        "--version",
        build_profile["version"],
        "--type",
        build_profile["type"],
        "--operation",
        build_profile["operation"],
        "--jobs",
        str(build_profile["jobs"]),
    ]

    run_env = os.environ.copy()
    run_env["UNIRTOS_EXTERNAL_APP_DIR"] = str(app_root)
    run_env["UNIRTOS_EXTERNAL_APP_NAME"] = app_root.name
    run_env["UNIRTOS_ROOT"] = str(env.get_unirtos_root(config))
    app_menuconfig_dir = app_root / "menuconfig"
    app_menuconfig_dir.mkdir(parents=True, exist_ok=True)
    run_env["UNIRTOS_APP_MENUCONFIG_DIR"] = str(app_menuconfig_dir)
    run_env["KCONFIG_CONFIG"] = str(app_menuconfig_dir / ".config")

    # Target name follows resolved version priority: CLI --version > env build.version > app root folder name.
    target_name = build_profile["version"]
    run_env["UNIRTOS_APP_TARGET_NAME"] = target_name
    
    # Library support: extract library list from config and pass as JSON environment variable
    libraries_config = config.get("libraries", {})
    if isinstance(libraries_config, dict) and "list" in libraries_config:
        import json as json_module
        libraries_list = libraries_config.get("list", [])
        if libraries_list:
            run_env["UNIRTOS_LIBRARIES_JSON"] = json_module.dumps(libraries_list)
            print(f"INFO: Found {len(libraries_list)} libraries to build: {[lib.get('name') for lib in libraries_list]}")

    print("\nINFO: Build Mode: SDK-driven (unirtos make)")
    print(f"INFO: SDK root: {sdk_path}")
    print(f"INFO: External app directory: {app_root}")
    print(f"INFO: SDK build profile: {build_profile}")
    print(f"INFO: Executing build command: {' '.join(cmd)}")

    try:
        # Stream compiler output line-by-line so users can see build progress in real time.
        process = subprocess.Popen(
            cmd,
            cwd=sdk_path,
            env=run_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        if process.stdout is not None:
            for line in process.stdout:
                print(line, end="", flush=True)

        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError("unirtos_make_failed")
    except RuntimeError as e:
        if str(e) != "unirtos_make_failed":
            raise
        raise RuntimeError(
            "'unirtos make' execution failed.\n"
            "Common Causes:\n"
            "1. build.module/version in env_config.json are invalid\n"
            "2. SDK CMake does not include external app injection logic\n"
            "3. External app CMakeLists.txt is not compatible with SDK add_subdirectory flow"
        )

    release_dir = app_root / "qos_build" / "release" / build_profile["version"]
    print(f"\nSUCCESS: Build completed successfully! Output directory: {release_dir}")

# ===================== Main Execution Flow =====================
def main() -> None:
    """
    Main execution entry point for the Unirtos build module.
    Implements full build lifecycle: argument parsing → config loading → 
    dependency validation → CMake configuration → compilation.
    """

    try:
        # Parse command line arguments
        args = parse_build_args()

        # Load environment configuration
        print("INFO: Loading environment configuration (env_config.json)...")
        config = load_unirtos_config()

        # Validate git availability (optional in SDK-driven mode)
        print("INFO: Validating git tool integrity (optional)...")
        try:
            env.check_git_installed(config)
        except Exception as git_err:
            print(f"WARNING: Git tool validation skipped: {git_err}")

        # Execute SDK-driven build process
        run_sdk_build(config, args)

    except KeyboardInterrupt:
        print("\nWARNING: Build process interrupted by user.")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\nERROR: Build failed: {str(e)}", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"\nCRITICAL ERROR: Unexpected build failure: {str(e)}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
