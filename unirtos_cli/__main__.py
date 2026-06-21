#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unirtos CLI Tool (Cross-Platform: Windows/Linux/macOS)
Core Functionality: 
  - Create Unirtos projects (new)
  - Initialize empty directories with Unirtos templates (init)
  - Execute environment configuration (env-setup)
  - Build Unirtos project (build)
  - Open Unirtos menuconfig (menuconfig)
  - Check CLI version (version)
  - List local/remote SDK versions (ls-sdk)
  - List local/remote library versions (ls-libs)
    - List demo versions from manifests (ls-demos)
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
import re

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
DEV_VERSION = "1.0.6"
UPDATE_INTERVAL = 3600
OFFICIAL_DEMO_MANIFEST_REPO_URL = "https://github.com/unirtos/unirtos-demos-manifests.git"

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

    # Cross-platform fallback: prefer explicit home env vars on Windows.
    if get_os_type() == "Windows":
        userprofile = os.environ.get("USERPROFILE", "").strip()
        if userprofile:
            return Path(userprofile).expanduser().absolute() / ".unirtos"

        homedrive = os.environ.get("HOMEDRIVE", "").strip()
        homepath = os.environ.get("HOMEPATH", "").strip()
        if homedrive and homepath:
            return Path(f"{homedrive}{homepath}").expanduser().absolute() / ".unirtos"

    home_env = os.environ.get("HOME", "").strip()
    if home_env:
        return Path(home_env).expanduser().absolute() / ".unirtos"

    return Path.home().expanduser().absolute() / ".unirtos"


def find_env_config(start_dir: Path) -> Path:
    """
    Search upward from start_dir for env_config.json.

    Args:
        start_dir: Directory to start searching from

    Returns:
        Path: Path to env_config.json if found, otherwise None
    """
    current_dir = start_dir.absolute()
    while True:
        config_file = current_dir / CONFIG_FILE_NAME
        if config_file.exists() and config_file.is_file():
            return config_file

        if current_dir.parent == current_dir:
            return None
        current_dir = current_dir.parent

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

    # Fallback: check main branch, then master branch
    refs_main = repo_dir / ".git" / "refs" / "heads" / "main"
    if refs_main.exists():
        return os.path.getmtime(refs_main)
    
    refs_master = repo_dir / ".git" / "refs" / "heads" / "master"
    if refs_master.exists():
        return os.path.getmtime(refs_master)
    
    return 0.0

def sync_manifest_repo(repo_url: str, target_dir: Path, config: dict = None, force: bool = False, specified_branch: str = "", silent: bool = False) -> None:
    """
    Clone or update manifest repository (reuse run_command from unirtos_env_setup).
    Supports branch fallback: specified_branch > main > master
    
    Args:
        repo_url: Remote URL of manifest repository
        target_dir: Local directory to store manifest repository
        config: Environment configuration dictionary (optional)
        force: Whether to force the execution of git pull (ignore time judgment)
        specified_branch: Branch to pull from. If empty, tries main first, then master.
        silent: Whether to suppress logs. Default is False.
    
    Raises:
        RuntimeError: If git clone/pull fails
    """
    env_setup = importlib.import_module("unirtos_cli.unirtos_env_setup")
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    
    if not (target_dir / ".git").exists():
        # If the repository does not exist: execute git clone
        env_setup.run_command(f"git clone {repo_url} {target_dir}", cwd=target_dir.parent, config=config, silent=silent)
    else:
        # If the repository exists: determine whether git pull is needed
        current_time = time.time()
        last_update_time = get_last_git_update_time(target_dir)
        time_diff = current_time - last_update_time
        
        if force or time_diff > UPDATE_INTERVAL:
            # Forced update or more than 1 hour has elapsed: execute git pull with branch fallback
            if specified_branch and specified_branch.strip():
                # User specified a branch
                specified_branch = specified_branch.strip()
                try:
                    if not silent:
                        print(f"Attempting to pull from specified branch '{specified_branch}'...", flush=True)
                    env_setup.run_command(f"git pull origin {specified_branch}", cwd=target_dir, config=config, silent=silent)
                    if not silent:
                        print(f"Successfully pulled from branch '{specified_branch}'", flush=True)
                except Exception as err:
                    raise RuntimeError(f"Failed to pull from specified branch '{specified_branch}': {str(err)}")
            else:
                # No branch specified, try main first, fallback to master
                try:
                    if not silent:
                        print(f"Attempting to pull from 'main' branch...", flush=True)
                    env_setup.run_command("git pull origin main", cwd=target_dir, config=config, silent=silent)
                    if not silent:
                        print(f"Successfully pulled from 'main' branch", flush=True)
                except Exception as main_err:
                    try:
                        if not silent:
                            print(f"INFO: Main branch pull failed, retrying with 'master' branch...", flush=True)
                        env_setup.run_command("git pull origin master", cwd=target_dir, config=config, silent=silent)
                        if not silent:
                            print(f"Successfully pulled from 'master' branch", flush=True)
                    except Exception as master_err:
                        raise RuntimeError(
                            f"Failed to pull from both 'main' and 'master' branches.\n"
                            f"Main error: {str(main_err)}\n"
                            f"Master error: {str(master_err)}"
                        )
        else:
            # Not timed out and not forced: skip pull
            pass


def _normalize_version_tag(version: str) -> str:
    """Normalize a semantic version string to tag format (vX.Y.Z)."""
    version = (version or "").strip()
    if not version:
        return ""
    return version if version.startswith("v") else f"v{version}"


def _strip_version_prefix(version: str) -> str:
    """Strip leading 'v' from version folder/tag name for display/path usage."""
    s = (version or "").strip()
    return s[1:] if s.startswith("v") else s


def _parse_version_key(version_name: str):
    """Parse version folder names like v1.2.3 for sorting, fallback to lexical."""
    s = (version_name or "").strip()
    if s.startswith("v"):
        s = s[1:]
    parts = re.split(r"[._-]", s)
    key = []
    for p in parts:
        if p.isdigit():
            key.append((0, int(p)))
        else:
            key.append((1, p))
    return key


def _resolve_project_name(raw_name: str) -> str:
    """Validate project name input and reject path-like values."""
    name = (raw_name or "").strip()
    if not name:
        raise RuntimeError("ERROR: project-name cannot be empty")
    if "/" in name or "\\" in name:
        raise RuntimeError(
            f"ERROR: project-name must be a plain name, not a path: '{name}'\n"
            "Resolution: Use 'unirtos-cli new <project-name> -d <project-dir>' for custom location."
        )
    if name in {".", ".."}:
        raise RuntimeError(f"ERROR: invalid project-name: '{name}'")
    return name


def _load_config_for_new(project_dir: Path) -> tuple:
    """
    Load config for 'new' flow from preferred locations.
    Priority: <project-dir>/env_config.json -> <cwd>/env_config.json -> empty config.
    """
    candidates = [project_dir / CONFIG_FILE_NAME, Path.cwd() / CONFIG_FILE_NAME]
    for cfg in candidates:
        if cfg.exists():
            with open(cfg, "r", encoding="utf-8") as f:
                return json.load(f), cfg
    return {}, None


def _resolve_new_target_dir(project_name: str, project_dir: str) -> Path:
    """Resolve target directory for new command from project-name and -d/--project-dir."""
    base_dir = Path(project_dir).absolute() if project_dir else Path.cwd()
    return base_dir / project_name


def _select_demo_manifest_file(demo_manifest_root: Path, demo_name: str, requested_version: str = "") -> tuple:
    """Pick demo manifest file under <demo>/<vX.Y.Z>/default.xml (specific or latest)."""
    demo_root = demo_manifest_root / demo_name
    if not demo_root.exists() or not demo_root.is_dir():
        raise RuntimeError(f"Demo not found in manifests: {demo_name}")

    version_dirs = []
    for item in demo_root.iterdir():
        if item.is_dir() and item.name.startswith("v") and (item / "default.xml").exists():
            version_dirs.append(item)

    if not version_dirs:
        raise RuntimeError(f"No valid demo versions found for '{demo_name}' in {demo_root}")

    if requested_version and requested_version.strip():
        requested_tag = _normalize_version_tag(requested_version)
        for version_dir in version_dirs:
            if _normalize_version_tag(version_dir.name) == requested_tag:
                return version_dir / "default.xml", version_dir.name

        available_versions = sorted(_strip_version_prefix(v.name) for v in version_dirs)
        raise RuntimeError(
            f"Requested demo version not found: {requested_version}\n"
            f"Available versions for '{demo_name}': {', '.join(available_versions)}"
        )

    version_dirs.sort(key=lambda p: _parse_version_key(p.name), reverse=True)
    selected_version_dir = version_dirs[0]
    return selected_version_dir / "default.xml", selected_version_dir.name


def _create_from_remote_demo(project_name: str, project_dir: Path, force: bool = False, requested_version: str = "") -> None:
    """Create project by cloning remote demo defined in demos manifest repository."""
    env_setup = importlib.import_module("unirtos_cli.unirtos_env_setup")

    config, config_path = _load_config_for_new(project_dir)
    unirtos_root = get_unirtos_root(config_path if config_path else None)

    demos_cfg = config.get("demos", {}) if isinstance(config, dict) else {}
    if not isinstance(demos_cfg, dict):
        demos_cfg = {}

    demo_manifest_url = demos_cfg.get("manifest_repo_url", "").strip() or OFFICIAL_DEMO_MANIFEST_REPO_URL
    demo_manifest_branch = demos_cfg.get("manifest_repo_branch", "").strip()
    demo_manifest_root = unirtos_root / "unirtos-demos-manifests"

    demo_manifest_root.parent.mkdir(parents=True, exist_ok=True)
    if not (demo_manifest_root / ".git").exists():
        print(f"INFO: Cloning demo manifest repository to: {demo_manifest_root}")
        env_setup.run_command(
            f"git clone {demo_manifest_url} {demo_manifest_root}",
            cwd=demo_manifest_root.parent,
            config=config,
        )
    elif force:
        print("INFO: Force updating demo manifest repository")
        sync_manifest_repo(
            demo_manifest_url,
            demo_manifest_root,
            config=config,
            force=True,
            specified_branch=demo_manifest_branch,
            silent=False,
        )
    else:
        print(f"INFO: Using local demo manifest repository: {demo_manifest_root}")

    manifest_file, demo_version_dir = _select_demo_manifest_file(
        demo_manifest_root,
        project_name,
        requested_version=requested_version,
    )
    demo_version = _strip_version_prefix(demo_version_dir)
    target_dir = project_dir / f"{project_name}-{demo_version}"

    print(f"INFO: Selected demo version: {demo_version}")
    print(f"INFO: Selected demo manifest: {manifest_file}")

    demo_projects = env_setup._collect_manifest_projects(demo_manifest_root, manifest_file)
    if not demo_projects:
        raise RuntimeError(f"No projects declared in demo manifest: {manifest_file}")

    # Prefer root project path='.'; fallback to first project.
    root_project = None
    for p in demo_projects:
        if p.get("path", "").strip() in {".", ""}:
            root_project = p
            break
    if root_project is None:
        root_project = demo_projects[0]

    repo_url = root_project.get("url", "").strip()
    if not repo_url:
        raise RuntimeError(f"Invalid demo repo URL in manifest: {manifest_file}")

    if target_dir.exists() and not is_dir_empty(target_dir):
        raise RuntimeError(
            f"ERROR: Project directory exists and is non-empty: {target_dir}\n"
            "Resolution: Use a new project name or delete the existing directory."
        )

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    print(f"INFO: Cloning demo repository: {repo_url}")
    env_setup.run_command(f"git clone {repo_url} {target_dir}", cwd=target_dir.parent, config=config)

    demo_version_tag = _normalize_version_tag(demo_version_dir)
    env_setup._checkout_revision(
        target_dir,
        root_project.get("revision", ""),
        config,
        prefer_tag=True,
        version_tag=demo_version_tag,
    )

    print(f"\nSUCCESS: Demo project '{project_name}-{demo_version}' created successfully from remote repo!")
    print("GUIDANCE:")
    print(f"  1. Navigate to project directory: cd {target_dir}")
    print("  2. Execute environment configuration: unirtos-cli env-setup")
    print("  3. Build project: unirtos-cli build")

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

def list_remote_sdk_versions(unirtos_root: Path, config: dict = None, force: bool = False, silent: bool = False) -> list:
    """
    List remote SDK versions from official manifest repository.
    
    Args:
        unirtos_root: Path to Unirtos root directory
        config: Environment configuration dictionary (optional)
        force: Whether to force update the manifest repository
        silent: Whether to suppress logs during sync. Default is False.
    
    Returns:
        list: Sorted list of remote SDK versions
    """
    env_setup = importlib.import_module("unirtos_cli.unirtos_env_setup")
    sdk_manifest_root = unirtos_root / "sdk" / "manifests"
    
    # Get branch from config if specified
    branch = ""
    if config and "sdk" in config:
        branch = config["sdk"].get("manifest_repo_branch", "").strip()
    
    # Sync manifest repository
    sync_manifest_repo(env_setup.OFFICIAL_SDK_MANIFEST_REPO_URL, sdk_manifest_root, config, force, specified_branch=branch, silent=silent)
    
    # Read version directories
    versions = []
    if sdk_manifest_root.exists():
        for item in sdk_manifest_root.iterdir():
            if item.is_dir() and item.name.startswith("v") and (item / "default.xml").exists():
                versions.append(item.name.lstrip("v"))
    return sorted(versions)

def list_remote_lib_versions(unirtos_root: Path, config: dict = None, force: bool = False, silent: bool = False) -> dict:
    """
    List remote library versions from official manifest repository.
    
    Args:
        unirtos_root: Path to Unirtos root directory
        config: Environment configuration dictionary (optional)
        force: Whether to force update the manifest repository
        silent: Whether to suppress logs during sync. Default is False.
    
    Returns:
        dict: Dictionary of library names and their remote versions
    """
    env_setup = importlib.import_module("unirtos_cli.unirtos_env_setup")
    lib_manifest_root = unirtos_root / "libraries" / "manifests"
    
    # Get branch from config if specified
    branch = ""
    if config and "libraries" in config:
        branch = config["libraries"].get("manifest_repo_branch", "").strip()
    
    # Sync manifest repository
    sync_manifest_repo(env_setup.OFFICIAL_LIB_MANIFEST_REPO_URL, lib_manifest_root, config, force, specified_branch=branch, silent=silent)
    
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


def list_local_demo_versions(unirtos_root: Path) -> dict:
    """
    List locally cached demo versions from demo manifest repository.

    Args:
        unirtos_root: Path to Unirtos root directory

    Returns:
        dict: Dictionary of demo names and their available versions
    """
    demo_manifest_root = unirtos_root / "unirtos-demos-manifests"
    demo_versions = {}
    if demo_manifest_root.exists():
        for demo_dir in demo_manifest_root.iterdir():
            if demo_dir.is_dir() and demo_dir.name != ".git":
                versions = []
                for ver_dir in demo_dir.iterdir():
                    if ver_dir.is_dir() and ver_dir.name.startswith("v") and (ver_dir / "default.xml").exists():
                        versions.append(ver_dir.name.lstrip("v"))
                if versions:
                    demo_versions[demo_dir.name] = sorted(versions)
    return demo_versions


def list_remote_demo_versions(unirtos_root: Path, config: dict = None, force: bool = False, silent: bool = False) -> dict:
    """
    List remote demo versions from official demo manifest repository.

    Args:
        unirtos_root: Path to Unirtos root directory
        config: Environment configuration dictionary (optional)
        force: Whether to force update the manifest repository
        silent: Whether to suppress logs during sync. Default is False.

    Returns:
        dict: Dictionary of demo names and their remote versions
    """
    demo_manifest_root = unirtos_root / "unirtos-demos-manifests"

    demos_cfg = config.get("demos", {}) if isinstance(config, dict) else {}
    if not isinstance(demos_cfg, dict):
        demos_cfg = {}

    branch = demos_cfg.get("manifest_repo_branch", "").strip()
    repo_url = demos_cfg.get("manifest_repo_url", "").strip() or OFFICIAL_DEMO_MANIFEST_REPO_URL

    sync_manifest_repo(repo_url, demo_manifest_root, config, force, specified_branch=branch, silent=silent)
    return list_local_demo_versions(unirtos_root)

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
            if data["type"] == "lib-local":
                title = "Installed libraries:"
            elif data["type"] == "lib-remote":
                title = "Remote libraries:"
            elif data["type"] == "demo-local":
                title = "Local demos:"
            elif data["type"] == "demo-remote":
                title = "Remote demos:"
            else:
                title = "Items:"
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
    Supports two modes:
    1. Template mode (default): create from app-tmpl
    2. Remote demo mode (--from-demo/-r): create from demo repository
    
    Args:
        args: Parsed command-line arguments
    
    Raises:
        RuntimeError: If target directory exists and is non-empty
    """
    if args.force and not args.from_demo:
        raise RuntimeError("ERROR: '--force/-f' is only valid when '--from-demo/-r' is specified.")
    if args.demo_version and not args.from_demo:
        raise RuntimeError("ERROR: '--version/-v' is only valid when '--from-demo/-r' is specified.")

    project_name = _resolve_project_name(args.project_name)

    if args.from_demo:
        _create_from_remote_demo(
            project_name,
            Path(args.project_dir).absolute() if args.project_dir else Path.cwd(),
            force=args.force,
            requested_version=args.demo_version,
        )
        return

    target_dir = _resolve_new_target_dir(project_name, args.project_dir)

    # Default template mode
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
    print("GUIDANCE:")
    print(f"  1. Navigate to project directory: cd {target_dir}")
    print("  2. Execute environment configuration: unirtos-cli env-setup")
    print("  3. Build project: unirtos-cli build")
    print("  4. For production use: Validate all critical files before deployment")

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
    Invokes package-internal build module with module/version (type=app, operation=r fixed).
    
    Args:
        args: Parsed command-line arguments (build_dir, jobs, module, version)
    
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
    print(f"INFO: Parallel jobs override: {args.jobs if args.jobs is not None else '(not set, use config/default)'}")

    try:
        # Import package-internal build module
        build_module = importlib.import_module("unirtos_cli.build")
        
        # Override sys.argv to pass build arguments to the module
        sys.argv = [
            sys.argv[0],
            "--build-dir", args.build_dir,
        ]

        if args.jobs is not None:
            sys.argv.extend(["--jobs", str(args.jobs)])
        if args.module:
            sys.argv.extend(["--module", args.module])
        if args.version:
            sys.argv.extend(["--version", args.version])
        
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

def handle_clean(args: argparse.Namespace) -> None:
    """
    Clean build artifacts command.
    Removes all build outputs from app directory (qos_build/).
    
    Args:
        args: Parsed command-line arguments (project_dir)
    
    Raises:
        RuntimeError: If config file is missing or clean fails
    """
    project_dir = Path(args.project_dir).absolute() if args.project_dir else Path.cwd()
    config_file = project_dir / CONFIG_FILE_NAME

    # Validate prerequisites
    if not config_file.exists():
        raise RuntimeError(f"ERROR: Configuration file not found: {config_file}\nRun 'unirtos-cli init' first.")

    print(f"INFO: Starting build artifact cleanup")
    print(f"INFO: Project directory: {project_dir}")

    try:
        # Import package-internal clean module
        clean_module = importlib.import_module("unirtos_cli.clean")
        
        # Set working directory to project directory
        original_cwd = os.getcwd()
        os.chdir(project_dir)
        
        # Execute clean module
        clean_module.main()
        
        # Restore original working directory
        os.chdir(original_cwd)
        
        print(f"\nSUCCESS: Build artifacts cleaned successfully!")
    except Exception as e:
        raise RuntimeError(f"ERROR: Clean failed: {str(e)}") from e

def handle_menuconfig(args: argparse.Namespace) -> None:
    """
    Open Unirtos menuconfig in SDK root (~/.unirtos/sdk/v<version>).

    Args:
        args: Parsed command-line arguments (project_dir)

    Raises:
        RuntimeError: If menuconfig execution fails
    """
    project_dir = Path(args.project_dir).absolute() if args.project_dir else Path.cwd()
    config_file = find_env_config(project_dir)
    if config_file is None:
        raise RuntimeError(
            f"ERROR: Configuration file not found from: {project_dir}\n"
            "Resolution: Run this command from your app root or its subdirectories, or specify '-d <project-dir>'."
        )

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    sdk_version = str(config.get("sdk", {}).get("version", "")).strip()
    if not sdk_version:
        raise RuntimeError(
            f"ERROR: 'sdk.version' is missing in {config_file}.\n"
            "Resolution: Set sdk.version in env_config.json first."
        )

    unirtos_root = get_unirtos_root(config_file)
    sdk_root = unirtos_root / "sdk" / f"v{sdk_version}"

    if not sdk_root.exists():
        raise RuntimeError(
            f"ERROR: SDK root directory not found: {sdk_root}\n"
            "Resolution: Run 'unirtos-cli env-setup' first to pull the specified SDK version."
        )

    print(f"INFO: Launching menuconfig in SDK root: {sdk_root}")
    try:
        subprocess.run(["unirtos", "menuconfig"], cwd=sdk_root, check=True)
        print("SUCCESS: menuconfig exited normally.")
    except FileNotFoundError as e:
        raise RuntimeError(
            "ERROR: 'unirtos' command not found.\n"
            "Resolution: Install Unirtos toolchain and ensure 'unirtos' is in PATH."
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ERROR: menuconfig execution failed (exit code={e.returncode}).") from e
    except Exception as e:
        raise RuntimeError(f"ERROR: Failed to launch menuconfig: {str(e)}") from e

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
        config_file = find_env_config(project_dir)
        unirtos_root = get_unirtos_root(config_file)
        
        # Load config for manifest sync
        config = {}
        if config_file and config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        
        # Get versions (local/remote)
        if args.remote:
            versions = list_remote_sdk_versions(unirtos_root, config, args.force, silent=args.json_output)
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
        config_file = find_env_config(project_dir)
        unirtos_root = get_unirtos_root(config_file)
        
        # Load config for manifest sync
        config = {}
        if config_file and config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        
        # Get versions (local/remote)
        if args.remote:
            lib_versions = list_remote_lib_versions(unirtos_root, config, args.force, silent=args.json_output)
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


def handle_ls_demos(args: argparse.Namespace) -> None:
    """
    Handle ls-demos command to list demo versions from manifest repository.

    Args:
        args: Parsed command-line arguments (project_dir, force, json_output)
    """
    try:
        project_dir = Path(args.project_dir).absolute() if args.project_dir else Path.cwd()
        config_file = find_env_config(project_dir)
        unirtos_root = get_unirtos_root(config_file)

        config = {}
        if config_file and config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

        demo_versions = list_remote_demo_versions(unirtos_root, config, args.force, silent=args.json_output)
        output_data = {
            "success": True,
            "message": "Demo versions fetched successfully",
            "type": "demo-remote",
            "data": demo_versions,
        }
    except Exception as e:
        output_data = {
            "success": False,
            "message": f"Failed to list demo versions: {str(e)}",
            "data": {},
        }

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
  1. Create new project from template:
     unirtos-cli new my-unirtos-app
  2. Create new project from remote demo:
     unirtos-cli new -r demo_a -d /path/to/workspace -f
  3. Create new project from remote demo with version:
     unirtos-cli new -r demo_a -v 1.0.0 -d /path/to/workspace
  3. Initialize empty directory with templates:
     mkdir empty-dir && cd empty-dir && unirtos-cli init
  4. Execute environment configuration:
     unirtos-cli env-setup -d /path/to/project
  5. Build project (default 4 parallel jobs):
     unirtos-cli build -d /path/to/project
  6. Build with custom parameters:
     unirtos-cli build --build-dir my-build --jobs 8
  7. Clean build artifacts:
     unirtos-cli clean -d /path/to/project
  8. Open menuconfig:
     unirtos-cli menuconfig -d /path/to/project
  9. Check version:
     unirtos-cli version
  10. List local SDK versions (human-readable):
      unirtos-cli ls-sdk
  11. List remote SDK versions (JSON output):
      unirtos-cli ls-sdk -r -j
  12. List remote SDK versions (force update manifest repo):
      unirtos-cli ls-sdk -r -f
  13. List remote library versions (force update + JSON output):
      unirtos-cli ls-libs -r -f -j
  14. List demo versions from manifests (force update + JSON output):
      unirtos-cli ls-demos -f -j
        """
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Core commands")

    # Subcommand: new (project creation)
    parser_new = subparsers.add_parser(
        "new",
        help="Create new Unirtos project (from template or remote demo)"
    )
    parser_new.add_argument(
        "project_name",
        metavar="project-name",
        help="Project name (plain name only, no path separators)"
    )
    parser_new.add_argument(
        "-r", "--from-demo",
        action="store_true",
        dest="from_demo",
        help="Create project by cloning remote demo repository"
    )
    parser_new.add_argument(
        "-v", "--version",
        dest="demo_version",
        default="",
        help="Demo version for remote demo mode (supports '1.0.0' or 'v1.0.0'; only valid with -r/--from-demo)"
    )
    parser_new.add_argument(
        "-d", "--project-dir",
        default=".",
        help="Base directory where <project-name> will be created (default: current working directory)"
    )
    parser_new.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force update demo manifest repo before selecting demo (only valid with -r/--from-demo)"
    )

    # Subcommand: init (core initialization)
    parser_init = subparsers.add_parser(
        "init",
        help="Initialize directory with Unirtos templates (empty dir) or validate files (non-empty dir)"
    )
    parser_init.add_argument(
        "-d", "--project-dir",
        default=".",
        help="Target directory (default: current working directory)"
    )

    # Subcommand: env_setup (environment configuration)
    parser_env_setup = subparsers.add_parser(
        "env-setup",
        help="Execute Unirtos environment configuration (post-initialization)"
    )
    parser_env_setup.add_argument(
        "-d", "--project-dir",
        default=".",
        help="Project directory (default: current working directory)"
    )

    # Subcommand: build (project compilation)
    parser_build = subparsers.add_parser(
        "build",
        help="Build Unirtos project (CMake + make compilation)"
    )
    parser_build.add_argument(
        "-d", "--project-dir",
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
        default=None,
        help="Number of parallel make jobs (priority: CLI > env_config build.jobs > 4)"
    )
    parser_build.add_argument(
        "-m", "--module",
        dest="module",
        default=None,
        help="SDK module/project name (e.g., EG800ZCN_LA)"
    )
    parser_build.add_argument(
        "-v", "--version",
        dest="version",
        default=None,
        help="SDK version string (e.g., EG800ZCNLAR01A01_BETA_OCPU_20260513)"
    )

    # Subcommand: clean (build artifact cleanup)
    parser_clean = subparsers.add_parser(
        "clean",
        help="Clean all build artifacts from app directory"
    )
    parser_clean.add_argument(
        "-d", "--project-dir",
        default=".",
        help="Project directory (default: current working directory)"
    )

    # Subcommand: menuconfig
    parser_menuconfig = subparsers.add_parser(
        "menuconfig",
        help="Open Unirtos menuconfig in SDK root (v<version>)"
    )
    parser_menuconfig.add_argument(
        "-d", "--project-dir",
        default=".",
        help="Project directory (to read env_config.json, default: current working directory)"
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
        "-d", "--project-dir",
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
        "-d", "--project-dir",
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

    # Subcommand: ls-demos (list demo versions)
    parser_ls_demos = subparsers.add_parser(
        "ls-demos",
        help="List local/remote demo versions"
    )
    parser_ls_demos.add_argument(
        "-d", "--project-dir",
        default=".",
        help="Project directory (to read env_config.json, default: current working directory)"
    )
    parser_ls_demos.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force update manifest repo (ignore 1-hour sync interval)"
    )
    parser_ls_demos.add_argument(
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
            "clean": handle_clean,
            "menuconfig": handle_menuconfig,
            "version": handle_version,
            "ls-sdk": handle_ls_sdk,
            "ls-libs": handle_ls_libs,
            "ls-demos": handle_ls_demos
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
