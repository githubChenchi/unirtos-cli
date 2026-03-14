#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unirtos Environment Setup Module
Core Functionality:
  - Validate Unirtos environment configuration
  - Pull SDK/libraries via package-internal repo tool
  - Manage Unirtos root directory structure
Copyright (c) [Your Company Name] [Year]. All Rights Reserved.
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

# Disable SSL certificate verification for GitHub resource download
ssl._create_default_https_context = ssl._create_unverified_context

# ===================== Core Configuration =====================
PACKAGE_NAME = "unirtos_cli"
UNIRTOS_CLI_NAME = "unirtos-cli"
TOOLS_DIR_NAME = "tools"
REPO_FILE_NAME = "repo"

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
    return Path.home() / ".unirtos"

def run_command(cmd, cwd=None, check=True):
    """
    Cross-platform execution of shell commands with package-internal repo tool.
    
    Args:
        cmd (str): Command string to be executed (supports 'repo' placeholder)
        cwd (Path, optional): Working directory for command execution
        check (bool, optional): Whether to check command execution result
    
    Returns:
        str: Standard output content of command execution
    
    Raises:
        CalledProcessError: When command execution fails
    """
    repo_path = str(get_repo_path())
    os_type = get_os_type()

    import shutil
    
    # Windows adaptation: execute repo via bash (require Git bash in PATH)
    if os_type == "Windows":
        python_cmd = "python" if shutil.which("python") else "python3"
        cmd = cmd.replace("repo", f"{python_cmd} {repo_path}")
        cmd = cmd.replace("\\", "/")
        cmd = f"bash -c '{cmd}'"
    else:
        # Linux/macOS direct replacement
        python_cmd = "python3" if shutil.which("python3") else "python"
        cmd = cmd.replace("repo", f"{python_cmd} {repo_path}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8"
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Command execution failed: {cmd}", flush=True)
        print(f"Error message: {e.stderr}", flush=True)
        raise

def check_repo_installed():
    """
    Validate package-internal 'repo' tool.
    
    Raises:
        RuntimeError: When repo tool is missing/invalid
    """
    try:
        run_command("repo --version", check=True)
        print(f"INFO: Package-internal repo tool is valid: {get_repo_path()}", flush=True)
    except Exception as e:
        raise RuntimeError(
            f"ERROR: Package-internal repo tool validation failed: {str(e)}\n"
            "Reference: https://gerrit.googlesource.com/git-repo/\n"
            "Resolution: Reinstall unirtos-cli package"
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
    Uses script-local repo tool.
    
    Args:
        config (dict): Environment configuration dictionary
    
    Raises:
        RuntimeError: Thrown when Manifest XML file for specified version does not exist
    """
    unirtos_root = get_unirtos_root(config)
    sdk_config = config["sdk"]
    sdk_version = sdk_config["version"]
    sdk_manifest_url = sdk_config["manifest_repo_url"]
    
    # SDK Manifest root directory (stores entire Master repository)
    sdk_manifest_root = unirtos_root / "sdk" / "manifests"
    # Specific version XML directory
    sdk_manifest_dir = sdk_manifest_root / f"v{sdk_version}"
    # SDK code storage directory
    sdk_code_dir = unirtos_root / "sdk" / f"v{sdk_version}"
    
    # Ensure directories exist
    sdk_manifest_root.mkdir(parents=True, exist_ok=True)
    sdk_code_dir.mkdir(parents=True, exist_ok=True)
    
    # Clone/update Master branch
    if not (sdk_manifest_root / ".git").exists():
        print(f"Cloning SDK Manifest repository (Master) to: {sdk_manifest_root}", flush=True)
        run_command(
            f"git clone {sdk_manifest_url} {sdk_manifest_root}",
            cwd=sdk_manifest_root.parent
        )
    else:
        print(f"Updating SDK Manifest repository (Master) to latest version", flush=True)
        run_command("git pull origin master", cwd=sdk_manifest_root)
    
    # Verify manifest file in version directory
    manifest_file = sdk_manifest_dir / "default.xml"
    if not manifest_file.exists():
        raise RuntimeError(f"Not found in SDK Manifest repository Master branch: {manifest_file}\nPlease check if v{sdk_version} directory is created and default.xml is placed inside")
    
    # Initialize and sync SDK code (use script-local repo)
    repo_cache = unirtos_root / "cache" / "sdk"
    repo_cache.mkdir(parents=True, exist_ok=True)
    
    if not (sdk_code_dir / ".repo").exists():
        run_command(
            f"repo init -u {sdk_manifest_root} -m v{sdk_version}/default.xml",
            cwd=sdk_code_dir
        )
    else:
        run_command(
            f"repo init -u {sdk_manifest_root} -m v{sdk_version}/default.xml",
            cwd=sdk_code_dir
        )
    
    print(f"Syncing SDK v{sdk_version} source code...", flush=True)
    run_command("repo sync -j4 --force-sync", cwd=sdk_code_dir)
    
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

def pull_lib(lib_config, unirtos_root):
    """
    Pull/update specified version of dependent library (based on single Master branch + component-version directory XML structure).
    Uses script-local repo tool.
    
    Args:
        lib_config (dict): Single library configuration dictionary
        unirtos_root (Path): Unirtos root directory path object
    
    Raises:
        RuntimeError: Thrown when library Manifest XML file for specified version does not exist
    """
    lib_name = lib_config["name"]
    lib_version = lib_config["version"]
    lib_manifest_url = lib_config["manifest_repo_url"]
    
    # Component Manifest root directory (stores entire Master repository)
    lib_manifest_root = unirtos_root / "libraries" / "manifests"
    # Component-version XML directory
    lib_manifest_dir = lib_manifest_root / lib_name / f"v{lib_version}"
    # Library code storage directory
    lib_code_dir = unirtos_root / "libraries" / lib_name / f"v{lib_version}"
    
    # Ensure directories exist
    lib_manifest_root.mkdir(parents=True, exist_ok=True)
    lib_code_dir.mkdir(parents=True, exist_ok=True)
    
    # Clone/update Master branch
    if not (lib_manifest_root / ".git").exists():
        print(f"Cloning component Manifest repository (Master) to: {lib_manifest_root}", flush=True)
        run_command(
            f"git clone {lib_manifest_url} {lib_manifest_root}",
            cwd=lib_manifest_root.parent
        )
    else:
        print(f"Updating component Manifest repository (Master) to latest version", flush=True)
        run_command("git pull origin master", cwd=lib_manifest_root)
    
    # Verify existence of default.xml in component-version directory
    manifest_file = lib_manifest_dir / "default.xml"
    if not manifest_file.exists():
        raise RuntimeError(f"Not found in component Manifest repository Master branch: {manifest_file}\nPlease check if {lib_name}/{lib_version} directory is created and default.xml is placed inside")
    
    # Initialize and sync library code (use script-local repo)
    repo_cache = unirtos_root / "cache" / "libraries"
    repo_cache.mkdir(parents=True, exist_ok=True)
    
    if not (lib_code_dir / ".repo").exists():
        run_command(
            f"repo init -u {lib_manifest_root} -m {lib_name}/v{lib_version}/default.xml",
            cwd=lib_code_dir
        )
    else:
        run_command(
            f"repo init -u {lib_manifest_root} -m {lib_name}/v{lib_version}/default.xml",
            cwd=lib_code_dir
        )
    
    print(f"Syncing {lib_name} v{lib_version} source code...", flush=True)
    run_command("repo sync -j4 --force-sync", cwd=lib_code_dir)
    
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
    unirtos_root = get_unirtos_root(config)
    for lib_config in config["libraries"]:
        print(f"\n--- Processing library: {lib_config['name']} v{lib_config['version']} ---", flush=True)
        if not check_lib_version(lib_config, unirtos_root):
            pull_lib(lib_config, unirtos_root)

# ===================== Main Process Module =====================
def main():
    """
    Unirtos environment initialization main process (local application version)
    Process Description:
    1. Parse command-line arguments and load configuration file
    2. Pre-check (script-local repo tool)
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
        
        # Pre-check (validate script-local repo tool)
        check_repo_installed()
        
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
        print("Dependent Libraries Paths:", flush=True)
        for lib in config["libraries"]:
            lib_version_dir = f"v{lib['version']}"
            print(f"  - {lib['name']}: {unirtos_root / 'libraries' / lib['name'] / lib_version_dir}", flush=True)
        print("\nNote: You can directly reference the above paths in local applications to build projects", flush=True)
    
    except Exception as e:
        print(f"\nEnvironment initialization failed: {str(e)}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
