#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unirtos Environment Setup Module
Core Functionality:
  - Validate Unirtos environment configuration
  - Pull SDK/libraries via package-internal repo tool
  - Manage Unirtos root directory structure
Copyright (c) Chavis.Chen 2026. All Rights Reserved.
"""

import os
import sys
import subprocess
import tarfile
import urllib.request
import json
import ssl
from pathlib import Path
import platform
import xml.etree.ElementTree as ET
import argparse
import importlib.resources as resources
from urllib.parse import urlparse
import re

# Disable SSL certificate verification for GitHub resource download
ssl._create_default_https_context = ssl._create_unverified_context

# ===================== Core Configuration =====================
PACKAGE_NAME = "unirtos_cli"
UNIRTOS_CLI_NAME = "unirtos-cli"
TOOLS_DIR_NAME = "tools"
REPO_FILE_NAME = "repo"
OFFICIAL_SDK_MANIFEST_REPO_URL = "https://github.com/unirtos/unirtos-sdk-manifests.git"
OFFICIAL_LIB_MANIFEST_REPO_URL = "https://github.com/unirtos/unirtos-libs-manifests.git"

SYSTEM_ENCODING = "gbk" if platform.system() == "Windows" else "utf-8"

# ===================== Command-line Argument Parsing =====================
def parse_args():
    """
    Parse command-line arguments for environment initialization.
    
    Returns:
        argparse.Namespace: Parsed arguments containing 'config' parameter
    """
    parser = argparse.ArgumentParser(description="Unirtos Environment Initialization Module")
    parser.add_argument("-c", "--config", required=True, help="Path to JSON configuration file")
    return parser.parse_args()

# ===================== Basic Utility Functions =====================
def get_os_type():
    """
    Get current operating system type (standardized for cross-platform compatibility).
    
    Returns:
        str: Operating system identifier (Windows/Linux/Darwin for macOS)
    """
    return platform.system()

def get_tools_dir() -> Path:
    """
    Get absolute path of tools directory (only for pip-installed package).
    
    Returns:
        Path: Absolute path to tools directory
    
    Raises:
        RuntimeError: If tools directory not found in package
    """
    try:
        with resources.path(PACKAGE_NAME, TOOLS_DIR_NAME) as tools_path:
            tools_path = tools_path.absolute()
            if tools_path.exists() and tools_path.is_dir():
                return tools_path
        raise FileNotFoundError(f"Tools directory {TOOLS_DIR_NAME} not found in package")
    except Exception as e:
        raise RuntimeError(
            f"Tools path resolution failed: {str(e)}\n"
            f"Resolution: Reinstall package with pip install --force-reinstall {UNIRTOS_CLI_NAME}"
        ) from e

def get_repo_path() -> Path:
    """
    Get absolute path of 'repo' tool from package tools directory.
    
    Returns:
        Path: Absolute path to 'repo' executable
    
    Raises:
        RuntimeError: If 'repo' file not found in tools directory
    """
    tools_dir = get_tools_dir()
    repo_path = tools_dir / REPO_FILE_NAME
    
    if not repo_path.exists():
        raise RuntimeError(
            f"'{REPO_FILE_NAME}' tool not found in tools directory: {repo_path}\n"
            "Resolution: Reinstall package with pip install --force-reinstall unirtos-cli"
        )
    
    # Add executable permission (Linux/macOS only)
    os_type = get_os_type()
    if os_type in ["Linux", "Darwin"] and not os.access(repo_path, os.X_OK):
        os.chmod(repo_path, 0o755)
        print(f"Granted executable permission to repo tool: {repo_path}", flush=True)
    
    return repo_path

def get_unirtos_root(config):
    """
    Get Unirtos root directory path (prioritize config path, use default if not specified).
    
    Args:
        config (dict): Environment configuration dictionary
    
    Returns:
        Path: Unirtos root directory path object
    """
    if config.get("unirtos_root") and config["unirtos_root"].strip():
        return Path(config["unirtos_root"]).expanduser().absolute()

    # Cross-platform fallback: prefer explicit home env vars on Windows.
    if platform.system() == "Windows":
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

def run_command(cmd, cwd=None, check=True, config=None):
    """
    Cross-platform execution of shell commands.
	
    Args:
        cmd (str): Command string to be executed
        cwd (Path, optional): Working directory for command execution
        check (bool, optional): Whether to check command execution result
        config (dict, optional): Env config dict
    
    Returns:
        str: Standard output content of command execution
    
    Raises:
        CalledProcessError: When command execution fails
    """
    env = os.environ.copy()

    stream_git_progress = bool(re.search(r"\bgit\s+(clone|pull|fetch|checkout)\b", cmd))
    
    try:
        if stream_git_progress:
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding=SYSTEM_ENCODING,
                errors="replace",
                env=env,
                creationflags=0,
                bufsize=1,
            )

            output_lines = []
            if process.stdout is not None:
                for line in process.stdout:
                    output_lines.append(line)
                    print(line, end="", flush=True)

            return_code = process.wait()
            output = "".join(output_lines)
            if check and return_code != 0:
                raise subprocess.CalledProcessError(return_code, cmd, output=output, stderr="")
            return output

        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding=SYSTEM_ENCODING,
            errors="replace",
            env=env,
            creationflags=0
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Command execution failed: {cmd}", flush=True)
        print(f"Error message: {e.stderr.strip()}", flush=True)
        raise

def check_git_installed(config):
    """
    Validate git tool availability.

    Args:
        config (dict): Env config dict

    Raises:
        RuntimeError: When git is missing/invalid
    """
    try:
        version = run_command("git --version", check=True, config=config).strip()
        print(f"INFO: Git tool is valid: {version}", flush=True)
    except Exception as e:
        raise RuntimeError(
            f"ERROR: Git tool validation failed: {str(e)}\n"
            "Resolution: Install Git and ensure 'git' is available in PATH"
        )


def _run_command_list(cmd_list, cwd=None, config=None):
    """Run command as list (no shell interpolation issues)."""
    env = os.environ.copy()
    stream_git_progress = (
        len(cmd_list) >= 2
        and cmd_list[0] == "git"
        and cmd_list[1] in {"clone", "pull", "fetch", "checkout"}
    )

    try:
        if stream_git_progress:
            process = subprocess.Popen(
                cmd_list,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding=SYSTEM_ENCODING,
                errors="replace",
                env=env,
                creationflags=0,
                bufsize=1,
            )

            output_lines = []
            if process.stdout is not None:
                for line in process.stdout:
                    output_lines.append(line)
                    print(line, end="", flush=True)

            return_code = process.wait()
            output = "".join(output_lines)
            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, cmd_list, output=output, stderr="")
            return output

        result = subprocess.run(
            cmd_list,
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding=SYSTEM_ENCODING,
            errors="replace",
            env=env,
            creationflags=0,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Command execution failed: {' '.join(cmd_list)}", flush=True)
        print(f"Error message: {(e.stderr or '').strip()}", flush=True)
        raise


def _looks_like_commit(revision: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{7,40}", revision or ""))


def _resolve_project_url(fetch: str, project_name: str) -> str:
    """Resolve project git URL from manifest remote.fetch + project.name."""
    fetch = (fetch or "").strip()
    project_name = (project_name or "").strip()
    if not fetch or not project_name:
        raise RuntimeError(f"invalid manifest project url fields: fetch='{fetch}', name='{project_name}'")

    # SCP-like git URL (git@host:org)
    if fetch.startswith("git@"):
        if fetch.endswith(":"):
            return f"{fetch}{project_name}"
        if fetch.endswith("/"):
            host_path = fetch[:-1].replace(":", ":", 1)
            if ":" in host_path:
                host, path = host_path.split(":", 1)
                return f"{host}:{path}/{project_name}"
        if ":" in fetch:
            return f"{fetch}/{project_name}"

    parsed = urlparse(fetch)
    if parsed.scheme:
        if fetch.endswith("/"):
            return f"{fetch}{project_name}"
        return f"{fetch}/{project_name}"

    # Local path style fetch (rare but supported)
    return str((Path(fetch) / project_name).as_posix())


def _collect_manifest_projects(manifest_root: Path, manifest_file: Path):
    """
    Parse repo-style manifest XML and return normalized project entries.
    Supported tags: remote/default/project/include/remove-project.
    """
    remotes = {}
    default_remote = None
    default_revision = "master"
    projects = []
    visited = set()

    def _parse_file(path: Path):
        nonlocal default_remote, default_revision
        path = path.resolve()
        if path in visited:
            return
        visited.add(path)

        if not path.exists():
            raise RuntimeError(f"Manifest file not found: {path}")

        tree = ET.parse(path)
        root = tree.getroot()
        if root.tag != "manifest":
            raise RuntimeError(f"Invalid manifest root in {path}, expected <manifest>")

        # First pass: remotes/default/include
        for elem in root:
            if elem.tag == "remote":
                name = elem.attrib.get("name", "").strip()
                fetch = elem.attrib.get("fetch", "").strip()
                if name:
                    remotes[name] = {
                        "fetch": fetch,
                        "revision": elem.attrib.get("revision", "").strip(),
                    }
            elif elem.tag == "default":
                if elem.attrib.get("remote", "").strip():
                    default_remote = elem.attrib.get("remote", "").strip()
                if elem.attrib.get("revision", "").strip():
                    default_revision = elem.attrib.get("revision", "").strip()
            elif elem.tag == "include":
                include_name = elem.attrib.get("name", "").strip()
                if include_name:
                    _parse_file((path.parent / include_name).resolve())

        # Second pass: projects and remove-project
        for elem in root:
            if elem.tag == "project":
                proj_name = elem.attrib.get("name", "").strip()
                if not proj_name:
                    continue
                proj_path = elem.attrib.get("path", proj_name).strip()
                proj_remote = elem.attrib.get("remote", "").strip() or default_remote
                proj_revision = elem.attrib.get("revision", "").strip() or default_revision
                proj_depth = elem.attrib.get("clone-depth", "").strip()
                projects.append(
                    {
                        "name": proj_name,
                        "path": proj_path,
                        "remote": proj_remote,
                        "revision": proj_revision,
                        "clone_depth": proj_depth,
                    }
                )
            elif elem.tag == "remove-project":
                remove_name = elem.attrib.get("name", "").strip()
                if remove_name:
                    projects[:] = [p for p in projects if p.get("name") != remove_name]

    _parse_file(manifest_file)

    normalized = []
    for p in projects:
        remote_name = p.get("remote", "")
        if remote_name not in remotes:
            raise RuntimeError(f"Manifest project '{p['name']}' references unknown remote '{remote_name}'")
        fetch = remotes[remote_name].get("fetch", "")
        revision = p.get("revision", "") or remotes[remote_name].get("revision", "") or default_revision
        normalized.append(
            {
                "name": p["name"],
                "path": p["path"],
                "url": _resolve_project_url(fetch, p["name"]),
                "revision": revision,
                "clone_depth": p.get("clone_depth", ""),
            }
        )

    return normalized


def _checkout_revision(repo_dir: Path, revision: str, config: dict):
    revision = (revision or "").strip()
    if not revision:
        return

    if revision.startswith("refs/heads/"):
        branch = revision.split("refs/heads/", 1)[1]
        _run_command_list(["git", "checkout", "-B", branch, f"origin/{branch}"], cwd=repo_dir, config=config)
        return

    if revision.startswith("refs/tags/"):
        tag = revision.split("refs/tags/", 1)[1]
        _run_command_list(["git", "checkout", tag], cwd=repo_dir, config=config)
        return

    if _looks_like_commit(revision):
        _run_command_list(["git", "checkout", revision], cwd=repo_dir, config=config)
        return

    # Generic branch/tag name fallback
    try:
        _run_command_list(["git", "checkout", "-B", revision, f"origin/{revision}"], cwd=repo_dir, config=config)
    except Exception:
        _run_command_list(["git", "checkout", revision], cwd=repo_dir, config=config)


def _sync_projects_from_manifest(manifest_root: Path, manifest_file: Path, work_root: Path, config: dict, context: str):
    projects = _collect_manifest_projects(manifest_root, manifest_file)
    if not projects:
        print(f"WARNING: No projects declared in manifest: {manifest_file}", flush=True)
        return

    print(f"INFO: Syncing {len(projects)} projects for {context} from manifest: {manifest_file}", flush=True)
    for idx, project in enumerate(projects, start=1):
        project_path = work_root / project["path"]
        project_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"[{idx}/{len(projects)}] {project['name']} -> {project['path']}", flush=True)

        if (project_path / ".git").exists():
            _run_command_list(["git", "fetch", "--all", "--tags", "--prune"], cwd=project_path, config=config)
        else:
            clone_cmd = ["git", "clone"]
            clone_depth = project.get("clone_depth", "")
            if clone_depth.isdigit() and int(clone_depth) > 0:
                clone_cmd.extend(["--depth", clone_depth])
            clone_cmd.extend([project["url"], str(project_path)])
            _run_command_list(clone_cmd, cwd=work_root, config=config)

        _checkout_revision(project_path, project.get("revision", ""), config)


def _try_pull_branch_with_fallback(repo_dir: Path, config: dict, specified_branch: str = ""):
    """
    Pull from specified branch, or fallback from main to master if no branch specified.
    
    Args:
        repo_dir (Path): Repository directory
        config (dict): Environment configuration
        specified_branch (str): Branch to pull from. If empty, tries main first, then master.
    
    Raises:
        RuntimeError: When pull attempts fail
    """
    if specified_branch and specified_branch.strip():
        # User specified a branch, use it
        specified_branch = specified_branch.strip()
        try:
            print(f"Attempting to pull from specified branch '{specified_branch}'...", flush=True)
            run_command(f"git pull origin {specified_branch}", cwd=repo_dir, config=config)
            print(f"Successfully pulled from branch '{specified_branch}'", flush=True)
            return
        except Exception as err:
            raise RuntimeError(f"Failed to pull from specified branch '{specified_branch}': {str(err)}")
    
    # No branch specified, try main first, fallback to master
    try:
        print(f"Attempting to pull from 'main' branch...", flush=True)
        run_command("git pull origin main", cwd=repo_dir, config=config)
        print(f"Successfully pulled from 'main' branch", flush=True)
        return
    except Exception as main_err:
        print(f"INFO: Main branch pull failed, retrying with 'master' branch...", flush=True)
    
    # Fallback to master branch
    try:
        print(f"Attempting to pull from 'master' branch...", flush=True)
        run_command("git pull origin master", cwd=repo_dir, config=config)
        print(f"Successfully pulled from 'master' branch", flush=True)
        return
    except Exception as master_err:
        raise RuntimeError(
            f"Failed to pull from both 'main' and 'master' branches.\n"
            f"Main error: {str(main_err)}\n"
            f"Master error: {str(master_err)}"
        )

def load_config(config_path):
    """
    Load JSON-formatted environment configuration file.
    
    Args:
        config_path (str): Path to configuration file
    
    Returns:
        dict: Parsed configuration dictionary
    
    Raises:
        RuntimeError: When configuration file does not exist
    """
    config_path = Path(config_path).absolute()
    if not config_path.exists():
        raise RuntimeError(f"Configuration file does not exist: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    print(f"Successfully loaded configuration file: {config_path}", flush=True)
    return config

# ===================== SDK Processing Functions =====================
def check_sdk_version(config):
    """
    Check if specified SDK version exists and matches.
    
    Args:
        config (dict): Environment configuration dictionary
    
    Returns:
        bool: True if SDK exists and version matches, otherwise False
    """
    unirtos_root = get_unirtos_root(config)
    sdk_version = config["sdk"]["version"]
    sdk_dir = unirtos_root / "sdk" / f"v{sdk_version}"
    version_file = sdk_dir / "version.txt"
    
    if version_file.exists():
        with open(version_file, "r") as f:
            current_version = f.read().strip()
        if current_version == sdk_version:
            print(f"SDK v{sdk_version} already exists and version matches", flush=True)
            return True
    print(f"SDK v{sdk_version} missing/version mismatch, starting pull process...", flush=True)
    return False

def pull_sdk(config):
    """
    Pull/update specified version of SDK (based on single Master branch + version directory XML structure).
    Uses manifest XML + git sync.
    
    Args:
        config (dict): Environment configuration dictionary
    
    Raises:
        RuntimeError: Thrown when Manifest XML file for specified version does not exist
    """
    unirtos_root = get_unirtos_root(config)
    sdk_config = config["sdk"]
    sdk_version = sdk_config["version"]

    sdk_manifest_url = sdk_config.get("manifest_repo_url", "").strip() or OFFICIAL_SDK_MANIFEST_REPO_URL
    print(f"INFO: Using SDK manifest repo URL: {sdk_manifest_url}", flush=True)
    
    # SDK Manifest root directory (stores entire Master repository)
    sdk_manifest_root = unirtos_root / "sdk" / "manifests"
    # Specific version XML directory
    sdk_manifest_dir = sdk_manifest_root / f"v{sdk_version}"
    # SDK code storage directory
    sdk_code_dir = unirtos_root / "sdk" / f"v{sdk_version}"
    
    # Ensure directories exist
    sdk_manifest_root.mkdir(parents=True, exist_ok=True)
    sdk_code_dir.mkdir(parents=True, exist_ok=True)
    
    # Clone/update manifest (try main first, fallback to master)
    if not (sdk_manifest_root / ".git").exists():
        print(f"Cloning SDK Manifest repository to: {sdk_manifest_root}", flush=True)
        run_command(
            f"git clone {sdk_manifest_url} {sdk_manifest_root}",
            cwd=sdk_manifest_root.parent,
            config=config
        )
    else:
        print(f"Updating SDK Manifest repository to latest version", flush=True)
        branch = sdk_config.get("manifest_repo_branch", "").strip()
        _try_pull_branch_with_fallback(sdk_manifest_root, config, specified_branch=branch)
    
    # Verify manifest file in version directory
    manifest_file = sdk_manifest_dir / "default.xml"
    if not manifest_file.exists():
        raise RuntimeError(f"Not found in SDK Manifest repository Master branch: {manifest_file}\nPlease check if v{sdk_version} directory is created and default.xml is placed inside")
    
    print(f"Syncing SDK v{sdk_version} source code...", flush=True)
    _sync_projects_from_manifest(
        manifest_root=sdk_manifest_root,
        manifest_file=manifest_file,
        work_root=sdk_code_dir,
        config=config,
        context=f"SDK v{sdk_version}",
    )
    
    # Write version identifier file
    with open(sdk_code_dir / "version.txt", "w") as f:
        f.write(sdk_version)
    print(f"SDK v{sdk_version} pull completed", flush=True)

# ===================== Library Processing Functions Module =====================
def check_lib_version(lib_config, unirtos_root):
    """
    Check if the specified version of dependent library exists and version matches.
    
    Args:
        lib_config (dict): Single library configuration dictionary
        unirtos_root (Path): Unirtos root directory path object
    
    Returns:
        bool: Returns True if library exists and version matches, otherwise False
    """
    lib_name = lib_config["name"]
    lib_version = lib_config["version"]
    lib_dir = unirtos_root / "libraries" / lib_name / f"v{lib_version}"
    version_file = lib_dir / "version.txt"
    
    if version_file.exists():
        with open(version_file, "r") as f:
            current_version = f.read().strip()
        if current_version == lib_version:
            print(f"Library {lib_name} v{lib_version} already exists and version matches", flush=True)
            return True
    print(f"Library {lib_name} v{lib_version} missing/version mismatch, starting pull process...", flush=True)
    return False

def prepare_lib_manifest_repo(config, unirtos_root):
    """
    Prepare library manifest repository (clone if not exists, update if exists)
    Execute only once before processing all libraries (optimization for efficiency)
    
    Args:
        config (dict): Env config dict
        unirtos_root (Path): Unirtos root directory path object
    
    Returns:
        Path: Path to library manifest root directory
    """
    # Get library manifest URL (fallback to official URL if not specified)
    lib_manifest_url = config["libraries"].get("manifest_repo_url", "").strip() or OFFICIAL_LIB_MANIFEST_REPO_URL
    lib_manifest_root = unirtos_root / "libraries" / "manifests"
    
    # Ensure parent directory exists
    lib_manifest_root.mkdir(parents=True, exist_ok=True)
    
    # Clone or update manifest repo (only once, try main first, fallback to master)
    if not (lib_manifest_root / ".git").exists():
        print(f"\n--- Cloning Library Manifest repository to: {lib_manifest_root} ---", flush=True)
        run_command(
            f"git clone {lib_manifest_url} {lib_manifest_root}",
            cwd=lib_manifest_root.parent,
            config=config
        )
    else:
        print(f"\n===== Updating Library Manifest repository to latest version =====", flush=True)
        branch = config["libraries"].get("manifest_repo_branch", "").strip()
        _try_pull_branch_with_fallback(lib_manifest_root, config, specified_branch=branch)
    
    print(f"INFO: Library Manifest repo preparation completed: {lib_manifest_root}", flush=True)
    return lib_manifest_root

def pull_lib(lib_config, unirtos_root, config, lib_manifest_root):
    """
    Pull/update specified version of dependent library (based on single Master branch + component-version directory XML structure).
    Uses manifest XML + git sync (optimized: no duplicate manifest repo clone/update)
    
    Args:
        lib_config (dict): Single library configuration dictionary
        unirtos_root (Path): Unirtos root directory path object
        config (dict): Env config dict
        lib_manifest_root (Path): Path to pre-prepared library manifest root directory
    Raises:
        RuntimeError: Thrown when library Manifest XML file for specified version does not exist
    """
    lib_name = lib_config["name"]
    lib_version = lib_config["version"]

    print(f"INFO: Processing library {lib_name} v{lib_version}", flush=True)
    
    # Component-version XML directory
    lib_manifest_dir = lib_manifest_root / lib_name / f"v{lib_version}"
    # Library code storage directory
    lib_code_dir = unirtos_root / "libraries" / lib_name / f"v{lib_version}"
    
    # Ensure directories exist
    lib_code_dir.mkdir(parents=True, exist_ok=True)
    
    # Verify existence of default.xml in component-version directory
    manifest_file = lib_manifest_dir / "default.xml"
    if not manifest_file.exists():
        raise RuntimeError(f"Not found in component Manifest repository Master branch: {manifest_file}\nPlease check if {lib_name}/{lib_version} directory is created and default.xml is placed inside")
    
    print(f"Syncing {lib_name} v{lib_version} source code...", flush=True)
    _sync_projects_from_manifest(
        manifest_root=lib_manifest_root,
        manifest_file=manifest_file,
        work_root=lib_code_dir,
        config=config,
        context=f"library {lib_name} v{lib_version}",
    )
    
    # Write version identifier file
    with open(lib_code_dir / "version.txt", "w") as f:
        f.write(lib_version)
    print(f"{lib_name} v{lib_version} pull completed", flush=True)

def batch_process_libraries(config):
    """
    Batch process all dependent libraries declared in configuration file (version check + pull/update).
    Args:
        config (dict): Environment configuration dictionary
    """
    # Check if the 'libraries' field exists
    if "libraries" not in config:
        print("\n===== Skip library processing: 'libraries' field not found in config =====", flush=True)
        return
    
    libraries_config = config["libraries"]
    # Check if the 'list' field exists, is a list type, and is non-empty
    if (
        "list" not in libraries_config 
        or not isinstance(libraries_config["list"], list) 
        or len(libraries_config["list"]) == 0
    ):
        print("\n===== Skip library processing: 'libraries.list' is missing, not a list, or empty =====", flush=True)
        return
    
	# Iterate over the 'list' field under 'libraries'
    unirtos_root = get_unirtos_root(config)
    lib_manifest_root = prepare_lib_manifest_repo(config, unirtos_root)
    for lib_config in libraries_config["list"]:
        print(f"\n--- Processing library: {lib_config['name']} v{lib_config['version']} ---", flush=True)
        if not check_lib_version(lib_config, unirtos_root):
            pull_lib(lib_config, unirtos_root, config, lib_manifest_root)

# ===================== Main Process Module =====================
def main():
    """
    Unirtos environment initialization main process (local application version)
    Process Description:
    1. Parse command-line arguments and load configuration file
    2. Pre-check (git tool)
    3. Check/pull specified version of SDK
    4. Batch process dependent libraries
    5. Output environment initialization result information
    """
    try:
        # Parse command-line arguments + load configuration
        args = parse_args()
        config = load_config(args.config)
        unirtos_root = get_unirtos_root(config)
        print(f"Unirtos common storage directory: {unirtos_root}", flush=True)
        
        # Pre-check (validate git tool)
        check_git_installed(config)

        # Process SDK
        print("\n===== Check/Pull SDK =====", flush=True)
        if not check_sdk_version(config):
            pull_sdk(config)
        
        # Batch process libraries
        print("\n===== Batch Process Dependent Libraries =====", flush=True)
        batch_process_libraries(config)
        
        # Output final environment information
        print("\n===== Environment initialization completed! =====", flush=True)
        sdk_version_dir = f"v{config['sdk']['version']}"
        print(f"SDK Path: {unirtos_root / 'sdk' / sdk_version_dir}", flush=True)
        
        # Output the library paths only when both 'libraries' and 'list' are valid
        if "libraries" in config and "list" in config["libraries"] and config["libraries"]["list"]:
            print("Dependent Libraries Paths:", flush=True)
            for lib in config["libraries"]["list"]:
                lib_version_dir = f"v{lib['version']}"
                print(f"  - {lib['name']}: {unirtos_root / 'libraries' / lib['name'] / lib_version_dir}", flush=True)
        else:
            print("Dependent Libraries Paths: No libraries configured")
        
        print("\nNote: You can directly reference the above paths in local applications to build projects", flush=True)
    
    except Exception as e:
        print(f"\nEnvironment initialization failed: {str(e)}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
