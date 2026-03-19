#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unirtos CLI Tool (Cross-Platform: Windows/Linux/macOS)
Core Functionality: 
  - Create Unirtos projects (new)
  - Initialize empty directories with Unirtos templates (init)
  - Execute environment configuration (env-setup)
  - Build Unirtos project (build)
  - Check CLI version (version)
  - List local/remote SDK versions (ls-sdk)
  - List local/remote library versions (ls-libs)
Copyright (c) Chavis.Chen 2026. All Rights Reserved.
"""

import os
import sys
import shutil
import subprocess
import platform
import json
import time
from pathlib import Path
import argparse
import importlib.resources as resources
import importlib

# ===================== Version Compatibility Handling =====================
try:
    from importlib.metadata import version as get_pkg_version, PackageNotFoundError
except ModuleNotFoundError:
    get_pkg_version = None
    PackageNotFoundError = Exception

# ===================== Core Configuration =====================
TMPL_DIR_NAME = "app-tmpl"
CONFIG_FILE_NAME = "env_config.json"
PACKAGE_NAME = "unirtos_cli"
UNIRTOS_CLI_NAME = "unirtos-cli"
DEV_VERSION = "0.1.4"
UPDATE_INTERVAL = 3600

# ===================== Core Utility Functions =====================
def get_os_type() -> str:
    """
    Get current operating system type (standardized for cross-platform compatibility).
    
    Returns:
        str: Operating system identifier (Windows/Linux/Darwin for macOS)
    """
    return platform.system()

def get_python_cmd() -> str:
    """
    Get cross-platform Python executable command (Python 3 prioritized).
    
    Returns:
        str: Valid Python command (python/python3)
    
    Raises:
        RuntimeError: If no Python interpreter is detected in system PATH
    """
    cmd_candidates = ["python3", "python"] if get_os_type() != "Windows" else ["python", "python3"]
    for cmd in cmd_candidates:
        if shutil.which(cmd):
            return cmd
    raise RuntimeError("ERROR: Python interpreter not found. Install Python 3.9+ and add to system PATH.")

def get_tmpl_dir() -> Path:
    """
    Resolve template directory path (only for pip-installed package).
    
    Returns:
        Path: Absolute path to template directory
    
    Raises:
        RuntimeError: If template directory not found in package
    """
    try:
        with resources.path(PACKAGE_NAME, TMPL_DIR_NAME) as tmpl_path:
            tmpl_path = tmpl_path.absolute()
            if tmpl_path.exists() and tmpl_path.is_dir():
                return tmpl_path
        raise FileNotFoundError(f"Template directory {TMPL_DIR_NAME} not found in package")
    except Exception as e:
        raise RuntimeError(
            f"Tools path resolution failed: {str(e)}\n"
            f"Resolution: Reinstall package with pip install --force-reinstall {UNIRTOS_CLI_NAME}"
        ) from e

def is_dir_empty(dir_path: Path, ignore_hidden: bool = False) -> bool:
    """
    Check if directory is empty.
    
    Args:
        dir_path: Target directory path to check
        ignore_hidden: Whether to ignore hidden files (starts with '.')
    
    Returns:
        bool: True if directory is empty, False otherwise
    """
    if not dir_path.exists():
        return True
    for item in dir_path.iterdir():
        if ignore_hidden and item.name.startswith('.'):
            continue
        return False
    return True

def copy_tmpl_to_target(tmpl_dir: Path, target_dir: Path) -> None:
    """
    Copy all template files to target directory.
    Preserves file permissions and supports cross-platform compatibility.
    
    Args:
        tmpl_dir: Source template directory (package-embedded or development)
        target_dir: Target application directory
    
    Raises:
        RuntimeError: If file copy operation fails (e.g., permission denied)
    """
    try:
        # Ensure target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Traverse all template files/subdirectories (no file type exclusion)
        for item in tmpl_dir.iterdir():
            if item.name == "__pycache__":
                continue
            target_item = target_dir / item.name
            if item.is_file():
                # Preserve file metadata (permissions, timestamps)
                shutil.copy2(item, target_item)
                
                # Enforce executable permission for 'repo' (Linux/macOS only)
                if item.name == "repo" and get_os_type() != "Windows":
                    os.chmod(target_item, 0o755)  # RWX for owner, RX for group/others
                print(f"SUCCESS: Copied template file: {item.name}")
            
            elif item.is_dir():
                # Recursive directory copy (overwrite existing for consistency)
                shutil.copytree(item, target_item, dirs_exist_ok=True)
                print(f"SUCCESS: Copied template directory: {item.name}/")
        
        print(f"\nINFO: Template files successfully copied to: {target_dir}")
    
    except Exception as e:
        raise RuntimeError(f"ERROR: Template copy failed: {str(e)}") from e

def get_unirtos_root(config_path: Path = None) -> Path:
    """
    Get Unirtos root directory path (prioritize config path, use default if not specified).
    
    Args:
        config_path: Path to env_config.json file (optional)
    
    Returns:
        Path: Absolute path to Unirtos root directory
    """
    config = {}
    if config_path and config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    
    if config.get("unirtos_root") and config["unirtos_root"].strip():
        return Path(config["unirtos_root"]).expanduser().absolute()
    return Path.home() / ".unirtos"

def get_last_git_update_time(repo_dir: Path) -> float:
    """
    Get the timestamp of the last update of the git repository (based on the modification time of the .git/FETCH_HEAD file)
    
    Args:
        repo_dir: Git repository directory path
    
    Returns:
        float: Last update timestamp (in seconds), returns 0 if the file does not exist
    """
    fetch_head = repo_dir / ".git" / "FETCH_HEAD"
    if fetch_head.exists():
        return os.path.getmtime(fetch_head)

    refs_head = repo_dir / ".git" / "refs" / "heads" / "master"
    if refs_head.exists():
        return os.path.getmtime(refs_head)
    return 0.0

def sync_manifest_repo(repo_url: str, target_dir: Path, config: dict = None, force: bool = False) -> None:
    """
    Clone or update manifest repository (reuse run_command from unirtos_env_setup).
    
    Args:
        repo_url: Remote URL of manifest repository
        target_dir: Local directory to store manifest repository
        config: Environment configuration dictionary (optional)
        force: Whether to force the execution of git pull (ignore time judgment)
    
    Raises:
        RuntimeError: If git clone/pull fails
    """
    env_setup = importlib.import_module("unirtos_cli.unirtos_env_setup")
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    
    if not (target_dir / ".git").exists():
        # If the repository does not exist: execute git clone
        env_setup.run_command(f"git clone {repo_url} {target_dir}", cwd=target_dir.parent, config=config)
    else:
        # If the repository exists: determine whether git pull is needed
        current_time = time.time()
        last_update_time = get_last_git_update_time(target_dir)
        time_diff = current_time - last_update_time
        
        if force or time_diff > UPDATE_INTERVAL:
            # Forced update or more than 1 hour has elapsed: execute git pull
            env_setup.run_command("git pull origin master", cwd=target_dir, config=config)
        else:
            # Not timed out and not forced: skip pull
            pass

def list_local_sdk_versions(unirtos_root: Path) -> list:
    """
    List locally installed SDK versions.
    
    Args:
        unirtos_root: Path to Unirtos root directory
    
    Returns:
        list: Sorted list of installed SDK versions
    """
    sdk_root = unirtos_root / "sdk"
    versions = []
    if sdk_root.exists():
        for item in sdk_root.iterdir():
            if item.is_dir() and item.name.startswith("v"):
                version_file = item / "version.txt"
                if version_file.exists():
                    with open(version_file, "r") as f:
                        ver = f.read().strip()
                    versions.append(ver)
    return sorted(versions)

def list_local_lib_versions(unirtos_root: Path) -> dict:
    """
    List locally installed library versions (key: lib name, value: version list).
    
    Args:
        unirtos_root: Path to Unirtos root directory
    
    Returns:
        dict: Dictionary of library names and their installed versions
    """
    lib_root = unirtos_root / "libraries"
    lib_versions = {}
    if lib_root.exists():
        for lib_dir in lib_root.iterdir():
            if lib_dir.is_dir() and lib_dir.name != "manifests":
                versions = []
                for ver_dir in lib_dir.iterdir():
                    if ver_dir.is_dir() and ver_dir.name.startswith("v"):
                        version_file = ver_dir / "version.txt"
                        if version_file.exists():
                            with open(version_file, "r") as f:
                                ver = f.read().strip()
                            versions.append(ver)
                if versions:
                    lib_versions[lib_dir.name] = sorted(versions)
    return lib_versions

def list_remote_sdk_versions(unirtos_root: Path, config: dict = None, force: bool = False) -> list:
    """
    List remote SDK versions from official manifest repository.
    
    Args:
        unirtos_root: Path to Unirtos root directory
        config: Environment configuration dictionary (optional)
        force: Whether to force update the manifest repository
    
    Returns:
        list: Sorted list of remote SDK versions
    """
    env_setup = importlib.import_module("unirtos_cli.unirtos_env_setup")
    sdk_manifest_root = unirtos_root / "sdk" / "manifests"
    
    # Sync manifest repository
    sync_manifest_repo(env_setup.OFFICIAL_SDK_MANIFEST_REPO_URL, sdk_manifest_root, config, force)
    
    # Read version directories
    versions = []
    if sdk_manifest_root.exists():
        for item in sdk_manifest_root.iterdir():
            if item.is_dir() and item.name.startswith("v") and (item / "default.xml").exists():
                versions.append(item.name.lstrip("v"))
    return sorted(versions)

def list_remote_lib_versions(unirtos_root: Path, config: dict = None, force: bool = False) -> dict:
    """
    List remote library versions from official manifest repository.
    
    Args:
        unirtos_root: Path to Unirtos root directory
        config: Environment configuration dictionary (optional)
        force: Whether to force update the manifest repository
    
    Returns:
        dict: Dictionary of library names and their remote versions
    """
    env_setup = importlib.import_module("unirtos_cli.unirtos_env_setup")
    lib_manifest_root = unirtos_root / "libraries" / "manifests"
    
    # Sync manifest repository
    sync_manifest_repo(env_setup.OFFICIAL_LIB_MANIFEST_REPO_URL, lib_manifest_root, config, force)
    
    # Read library and version directories
    lib_versions = {}
    if lib_manifest_root.exists():
        for lib_dir in lib_manifest_root.iterdir():
            if lib_dir.is_dir():
                versions = []
                for ver_dir in lib_dir.iterdir():
                    if ver_dir.is_dir() and ver_dir.name.startswith("v") and (ver_dir / "default.xml").exists():
                        versions.append(ver_dir.name.lstrip("v"))
                if versions:
                    lib_versions[lib_dir.name] = sorted(versions)
    return lib_versions

def format_output(data: dict, is_json: bool) -> None:
    """
    Format output as JSON or human-readable text.
    
    Args:
        data: Output data dictionary with structure:
              {"success": bool, "message": str, "type": str, "data": list/dict}
        is_json: Whether to output in JSON format
    """
    if is_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if not data["success"]:
            print(f"ERROR: {data['message']}")
            return
        
        # Handle SDK output
        if isinstance(data["data"], list):
            title = "Installed SDK versions:" if data["type"] == "sdk-local" else "Remote SDK versions:"
            print(title)
            if data["data"]:
                for ver in data["data"]:
                    print(f"  - {ver}")
            else:
                print("  (no versions found)")
        
        # Handle library output
        elif isinstance(data["data"], dict):
            title = "Installed libraries:" if data["type"] == "lib-local" else "Remote libraries:"
            print(title)
            if data["data"]:
                for lib_name, versions in data["data"].items():
                    ver_str = ", ".join(versions) if versions else "no versions"
                    print(f"  {lib_name}: {ver_str}")
            else:
                print("  (no libraries found)")

# ===================== Command Handler Functions =====================
def handle_init(args: argparse.Namespace) -> None:
    """
    Core initialization command.
    Key functionality:
    1. Copy template files to empty target directory
    2. Validate critical file integrity
    3. Ensure compliance with Unirtos application structure
    
    Args:
        args: Parsed command-line arguments (contains project_dir)
    
    Raises:
        RuntimeError: If critical files are missing
    """
    project_dir = Path(args.project_dir).absolute() if args.project_dir else Path.cwd()
    print(f"INFO: Starting Unirtos environment initialization: {project_dir}")

    if is_dir_empty(project_dir):
        print(f"INFO: Target directory is empty - deploying Unirtos templates...")
        tmpl_dir = get_tmpl_dir()
        copy_tmpl_to_target(tmpl_dir, project_dir)
    else:
        print(f"WARNING: Target directory is not empty - skipping template deployment (only validating files)")

    # Validate critical file presence 
    critical_files = {
        "configuration file": project_dir / CONFIG_FILE_NAME
    }

    missing_files = []
    for file_desc, file_path in critical_files.items():
        if not file_path.exists():
            missing_files.append(f"{file_desc} ({file_path.name})")

    if missing_files:
        error_guide = "\n".join([
            "Corrective Actions:",
            f"1. Re-run 'unirtos-cli init' in an EMPTY directory to deploy full templates",
            f"2. Manually restore missing files to: {project_dir}",
            f"3. Reinstall Unirtos CLI: pip install --force-reinstall {UNIRTOS_CLI_NAME}"
        ])
        raise RuntimeError(
            f"ERROR: Critical Unirtos files missing: {', '.join(missing_files)}\n{error_guide}"
        )

    print("SUCCESS: Unirtos environment initialization completed (template deployment + integrity check passed).")

def handle_new_project(args: argparse.Namespace) -> None:
    """
    Project creation command.
    Streamlines workflow: Create new directory → Initialize with templates.
    
    Args:
        args: Parsed command-line arguments (contains project_name)
    
    Raises:
        RuntimeError: If target directory exists and is non-empty
    """
    project_name = args.project_name
    target_dir = Path(project_name).absolute()

    if target_dir.exists():
        if not is_dir_empty(target_dir):
            raise RuntimeError(
                f"ERROR: Project directory exists and is non-empty: {target_dir}\n"
                "Resolution: Use a new project name or delete the existing directory."
            )
        print(f"WARNING: Project directory exists (empty) - reinitializing templates: {target_dir}")
    else:
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"INFO: Created new Unirtos project directory: {target_dir}")

    init_args = argparse.Namespace(project_dir=str(target_dir))
    handle_init(init_args)

    print(f"\nSUCCESS: Unirtos project '{project_name}' created successfully!")
    print(f"GUIDANCE:")
    print(f"  1. Navigate to project directory: cd {project_name}")
    print(f"  2. Execute environment configuration: unirtos-cli env-setup")
    print(f"  3. Build project: unirtos-cli build")
    print(f"  4. For production use: Validate all critical files before deployment")

def handle_env_setup(args: argparse.Namespace) -> None:
    """
    Environment configuration execution command.
    Executes the package-internal Unirtos environment setup module.
    
    Args:
        args: Parsed command-line arguments (contains project_dir)
    
    Raises:
        RuntimeError: If configuration file is missing or execution fails
    """
    project_dir = Path(args.project_dir).absolute() if args.project_dir else Path.cwd()
    config_file = project_dir / CONFIG_FILE_NAME

    if not config_file.exists():
        raise RuntimeError(f"ERROR: Configuration file not found: {config_file}\nRun 'unirtos-cli init' first.")

    print(f"INFO: Executing Unirtos environment setup")
    print(f"INFO: Configuration file: {config_file}")

    try:
        # Import package-internal setup module
        env_setup = importlib.import_module("unirtos_cli.unirtos_env_setup")
        
        # Mock command line arguments for setup module
        sys.argv = [sys.argv[0], "--config", str(config_file)]
        env_setup.main()
        
        print(f"\nSUCCESS: Environment configuration executed successfully!")
    except Exception as e:
        raise RuntimeError(f"ERROR: Setup module failed: {str(e)}") from e

def handle_build(args: argparse.Namespace) -> None:
    """
    Project build command.
    Invokes package-internal build module with user-specified build parameters.
    
    Args:
        args: Parsed command-line arguments (build_dir, jobs, project_dir)
    
    Raises:
        RuntimeError: If build process fails (config missing/CMake error/make error)
    """
    project_dir = Path(args.project_dir).absolute() if args.project_dir else Path.cwd()
    config_file = project_dir / CONFIG_FILE_NAME

    # Validate prerequisites
    if not config_file.exists():
        raise RuntimeError(f"ERROR: Configuration file not found: {config_file}\nRun 'unirtos-cli init' first.")

    print(f"INFO: Starting Unirtos project build")
    print(f"INFO: Project directory: {project_dir}")
    print(f"INFO: Build directory: {args.build_dir}")
    print(f"INFO: Parallel jobs: {args.jobs}")

    try:
        # Import package-internal build module
        build_module = importlib.import_module("unirtos_cli.build")
        
        # Override sys.argv to pass build arguments to the module
        sys.argv = [
            sys.argv[0],
            "--build-dir", args.build_dir,
            "--jobs", str(args.jobs)
        ]
        
        # Set working directory to project directory (critical for CMake)
        original_cwd = os.getcwd()
        os.chdir(project_dir)
        
        # Execute build module
        build_module.main()
        
        # Restore original working directory
        os.chdir(original_cwd)
        
        print(f"\nSUCCESS: Unirtos project built successfully!")
    except Exception as e:
        raise RuntimeError(f"ERROR: Build process failed: {str(e)}") from e

def handle_version(args: argparse.Namespace) -> None:
    """
    Version information command.
    Supports both installed (PyPI) and development versions.
    
    Args:
        args: Parsed command-line arguments (unused for version command)
    """
    if get_pkg_version is not None:
        try:
            pkg_version = get_pkg_version(UNIRTOS_CLI_NAME)
            print(f"{UNIRTOS_CLI_NAME} v{pkg_version}")
            return
        except PackageNotFoundError:
            print(f"{UNIRTOS_CLI_NAME} v{DEV_VERSION} (Development Build)")
        except Exception as e:
            print(f"{UNIRTOS_CLI_NAME} v{DEV_VERSION} (Version Detection Failed: {str(e)[:50]})")
    else:
        print(f"{UNIRTOS_CLI_NAME} v{DEV_VERSION} (Legacy Python: {sys.version.split()[0]})")

def handle_ls_sdk(args: argparse.Namespace) -> None:
    """
    Handle ls-sdk command to list local/remote SDK versions.
    
    Args:
        args: Parsed command-line arguments (project_dir, remote, json_output)
    """
    try:
        # Get config file path and Unirtos root directory
        project_dir = Path(args.project_dir).absolute() if args.project_dir else Path.cwd()
        config_file = project_dir / CONFIG_FILE_NAME
        unirtos_root = get_unirtos_root(config_file if config_file.exists() else None)
        
        # Load config for manifest sync
        config = {}
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        
        # Get versions (local/remote)
        if args.remote:
            versions = list_remote_sdk_versions(unirtos_root, config, args.force)
            output_data = {
                "success": True,
                "message": "Remote SDK versions fetched successfully",
                "type": "sdk-remote",
                "data": versions
            }
        else:
            versions = list_local_sdk_versions(unirtos_root)
            output_data = {
                "success": True,
                "message": "Local SDK versions fetched successfully",
                "type": "sdk-local",
                "data": versions
            }
    except Exception as e:
        output_data = {
            "success": False,
            "message": f"Failed to list SDK versions: {str(e)}",
            "data": []
        }
    
    # Format and print output
    format_output(output_data, args.json_output)

def handle_ls_libs(args: argparse.Namespace) -> None:
    """
    Handle ls-libs command to list local/remote library versions.
    
    Args:
        args: Parsed command-line arguments (project_dir, remote, json_output)
    """
    try:
        # Get config file path and Unirtos root directory
        project_dir = Path(args.project_dir).absolute() if args.project_dir else Path.cwd()
        config_file = project_dir / CONFIG_FILE_NAME
        unirtos_root = get_unirtos_root(config_file if config_file.exists() else None)
        
        # Load config for manifest sync
        config = {}
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        
        # Get versions (local/remote)
        if args.remote:
            lib_versions = list_remote_lib_versions(unirtos_root, config, args.force)
            output_data = {
                "success": True,
                "message": "Remote library versions fetched successfully",
                "type": "lib-remote",
                "data": lib_versions
            }
        else:
            lib_versions = list_local_lib_versions(unirtos_root)
            output_data = {
                "success": True,
                "message": "Local library versions fetched successfully",
                "type": "lib-local",
                "data": lib_versions
            }
    except Exception as e:
        output_data = {
            "success": False,
            "message": f"Failed to list library versions: {str(e)}",
            "data": {}
        }
    
    # Format and print output
    format_output(output_data, args.json_output)

# ===================== Command Line Interface =====================
def build_arg_parser() -> argparse.ArgumentParser:
    """
    Build command-line argument parser compliant with POSIX standards.
    
    Returns:
        argparse.ArgumentParser: Configured parser with subcommands
    """
    parser = argparse.ArgumentParser(
        prog="unirtos-cli",
        description="Unirtos CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage Examples:
  1. Create new project (directory + initialization):
     unirtos-cli new my-unirtos-app
  2. Initialize empty directory with templates:
     mkdir empty-dir && cd empty-dir && unirtos-cli init
  3. Execute environment configuration:
     unirtos-cli env-setup -d /path/to/project
  4. Build project (default 4 parallel jobs):
     unirtos-cli build -d /path/to/project
  5. Build with custom parameters:
     unirtos-cli build --build-dir my-build --jobs 8
  6. Check version:
     unirtos-cli version
  7. List local SDK versions (human-readable):
     unirtos-cli ls-sdk
  8. List remote SDK versions (JSON output):
     unirtos-cli ls-sdk -r -j
  9. List remote SDK versions (force update manifest repo):
     unirtos-cli ls-sdk -r -f
  10. List remote library versions (force update + JSON output):
      unirtos-cli ls-libs -r -f -j
        """
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Core commands")

    # Subcommand: new (project creation)
    parser_new = subparsers.add_parser(
        "new",
        help="Create new Unirtos project (directory creation + template deployment)"
    )
    parser_new.add_argument(
        "project_name",
        help="Project name (will create directory with this name)"
    )

    # Subcommand: init (core initialization)
    parser_init = subparsers.add_parser(
        "init",
        help="Initialize directory with Unirtos templates (empty dir) or validate files (non-empty dir)"
    )
    parser_init.add_argument(
        "-d", "--project_dir",
        default=".",
        help="Target directory (default: current working directory)"
    )

    # Subcommand: env_setup (environment configuration)
    parser_env_setup = subparsers.add_parser(
        "env-setup",
        help="Execute Unirtos environment configuration (post-initialization)"
    )
    parser_env_setup.add_argument(
        "-d", "--project_dir",
        default=".",
        help="Project directory (default: current working directory)"
    )

    # Subcommand: build (project compilation)
    parser_build = subparsers.add_parser(
        "build",
        help="Build Unirtos project (CMake + make compilation)"
    )
    parser_build.add_argument(
        "-d", "--project_dir",
        default=".",
        help="Project directory (default: current working directory)"
    )
    parser_build.add_argument(
        "-b", "--build-dir",
        default="build",
        help="CMake build directory (default: build/)"
    )
    parser_build.add_argument(
        "-j", "--jobs",
        type=int,
        default=4,
        help="Number of parallel make jobs (default: 4, optimizes compilation speed)"
    )

    # Subcommand: version (version information)
    parser_version = subparsers.add_parser(
        "version",
        help="Display Unirtos CLI version"
    )

    # Subcommand: ls-sdk (list SDK versions)
    parser_ls_sdk = subparsers.add_parser(
        "ls-sdk",
        help="List local/remote SDK versions"
    )
    parser_ls_sdk.add_argument(
        "-d", "--project_dir",
        default=".",
        help="Project directory (to read env_config.json, default: current working directory)"
    )
    parser_ls_sdk.add_argument(
        "-l", "--local",
        action="store_false",
        dest="remote",
        default=False,
        help="List local SDK versions (default)"
    )
    parser_ls_sdk.add_argument(
        "-r", "--remote",
        action="store_true",
        help="List remote SDK versions from official manifest repo"
    )
    parser_ls_sdk.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force update manifest repo (ignore 1-hour sync interval, only for remote query)"
    )
    parser_ls_sdk.add_argument(
        "-j", "--json-output",
        action="store_true",
        help="Output result in JSON format"
    )

    # Subcommand: ls-libs (list library versions)
    parser_ls_libs = subparsers.add_parser(
        "ls-libs",
        help="List local/remote library versions"
    )
    parser_ls_libs.add_argument(
        "-d", "--project_dir",
        default=".",
        help="Project directory (to read env_config.json, default: current working directory)"
    )
    parser_ls_libs.add_argument(
        "-l", "--local",
        action="store_false",
        dest="remote",
        default=False,
        help="List local library versions (default)"
    )
    parser_ls_libs.add_argument(
        "-r", "--remote",
        action="store_true",
        help="List remote library versions from official manifest repo"
    )
    parser_ls_libs.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force update manifest repo (ignore 1-hour sync interval, only for remote query)"
    )
    parser_ls_libs.add_argument(
        "-j", "--json-output",
        action="store_true",
        help="Output result in JSON format"
    )

    return parser

# ===================== Main Entry Point =====================
def main() -> None:
    """
    Main entry point for Unirtos CLI with robust error handling.
    """
    try:
        parser = build_arg_parser()
        args = parser.parse_args()

        command_handlers = {
            "new": handle_new_project,
            "init": handle_init,
            "env-setup": handle_env_setup,
            "build": handle_build,
            "version": handle_version,
            "ls-sdk": handle_ls_sdk,
            "ls-libs": handle_ls_libs
        }

        if args.command in command_handlers:
            command_handlers[args.command](args)
        else:
            parser.print_help()

    except RuntimeError as e:
        print(f"\nERROR: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nWARNING: Operation interrupted by user - Unirtos CLI aborted.")
        sys.exit(0)
    except Exception as e:
        print(f"\nCRITICAL ERROR: Unirtos CLI execution failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
