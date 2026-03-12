#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unirtos CLI Tool (Cross-Platform: Windows/Linux/macOS)
Core Functionality: 
  - Create Unirtos application projects (new)
  - Initialize empty directories with Unirtos templates (init)
  - Execute environment configuration scripts (env_setup)
  - Check CLI version (version)
Copyright (c) [Your Company Name] [Year]. All Rights Reserved.
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path
import argparse
import importlib.resources as resources

# ===================== Version Compatibility Handling =====================
# Compatibility for Python <3.8 (importlib.metadata backport)
try:
    from importlib.metadata import version as get_pkg_version, PackageNotFoundError
except ModuleNotFoundError:
    get_pkg_version = None
    PackageNotFoundError = Exception

# ===================== Core Configuration =====================
# Template directory name (embedded in package)
TMPL_DIR_NAME = "app-tmpl"
# Environment setup script filename (critical for runtime configuration)
SETUP_SCRIPT_NAME = "unirtos_env_setup.py"
# Environment configuration filename (JSON format)
CONFIG_FILE_NAME = "env_config.json"
# Package name (must match 'name' in setup.cfg for PyPI distribution)
PACKAGE_NAME = "unirtos-cli"
# Fallback development version (used when package is not installed via Pip)
DEV_VERSION = "0.1.1"

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
    Resolve template directory path (PyPI-compliant, cross-platform).
    Priority: Package embedded templates > Development mode templates.
    
    Returns:
        Path: Valid absolute path to template directory
    
    Raises:
        RuntimeError: If no valid template directory is found
    """
    try:
        # PyPI installation: read from package resources
        with resources.path(PACKAGE_NAME, TMPL_DIR_NAME) as tmpl_dir:
            if tmpl_dir.exists() and tmpl_dir.is_dir():
                return tmpl_dir
    except ModuleNotFoundError:
        # Development mode: read from source code directory (for internal testing)
        base_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
        tmpl_dir = base_dir / TMPL_DIR_NAME
        if tmpl_dir.exists():
            return tmpl_dir
    except Exception as e:
        raise RuntimeError(f"ERROR: Template path resolution failed: {str(e)}") from e

    # Error resolution guidance
    resolution_guide = "\n".join([
        "Resolution Steps:",
        f"1. Verify {TMPL_DIR_NAME} exists in the package distribution",
        f"2. Reinstall package: pip install --force-reinstall {PACKAGE_NAME}",
        f"3. For development: Ensure {TMPL_DIR_NAME} is in the package root directory"
    ])
    raise RuntimeError(f"ERROR: Valid {TMPL_DIR_NAME} directory not found!\n{resolution_guide}")

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
    Preserves file permissions (critical for executable files like 'repo') and supports:
    - Hidden files (e.g., .gitignore)
    - Extensionless files (e.g., repo)
    - Cross-platform permission compatibility
    
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

# ===================== Command Handler Functions =====================
def handle_init(args: argparse.Namespace) -> None:
    """
    Core initialization command.
    Key functionality:
    1. Copy template files to empty target directory (primary use case)
    2. Validate critical file integrity (non-empty directories)
    3. Ensure compliance with Unirtos application structure
    
    Args:
        args: Parsed command-line arguments (contains project_dir)
    
    Raises:
        RuntimeError: If critical files are missing (non-empty directories)
    """
    # Resolve target directory (default to current working directory)
    project_dir = Path(args.project_dir).absolute() if args.project_dir else Path.cwd()
    print(f"INFO: Starting Unirtos environment initialization: {project_dir}")

    # Step 1: Copy templates if directory is empty
    if is_dir_empty(project_dir):
        print(f"INFO: Target directory is empty - deploying Unirtos templates...")
        tmpl_dir = get_tmpl_dir()
        copy_tmpl_to_target(tmpl_dir, project_dir)
    else:
        print(f"WARNING: Target directory is not empty - skipping template deployment (only validating files)")

    # Step 2: Validate critical file presence
    critical_files = {
        "environment setup script": project_dir / SETUP_SCRIPT_NAME,
        "configuration file": project_dir / CONFIG_FILE_NAME,
        "repo utility": project_dir / "repo"
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
            f"3. Reinstall Unirtos CLI: pip install --force-reinstall {PACKAGE_NAME}"
        ])
        raise RuntimeError(
            f"ERROR: Critical Unirtos files missing: {', '.join(missing_files)}\n{error_guide}"
        )

    # Final validation confirmation
    print("SUCCESS: Unirtos environment initialization completed (template deployment + integrity check passed).")

def handle_new_project(args: argparse.Namespace) -> None:
    """
    Project creation command.
    Streamlines workflow: Create new directory → Initialize with templates.
    Eliminates redundant template copy logic (reuses core init functionality).
    
    Args:
        args: Parsed command-line arguments (contains project_name)
    
    Raises:
        RuntimeError: If target directory exists and is non-empty
    """
    # Resolve new project directory
    project_name = args.project_name
    target_dir = Path(project_name).absolute()

    # Validate directory state
    if target_dir.exists():
        if not is_dir_empty(target_dir):
            raise RuntimeError(
                f"ERROR: Project directory exists and is non-empty: {target_dir}\n"
                "Resolution: Use a new project name or delete the existing directory."
            )
        print(f"WARNING: Project directory exists (empty) - reinitializing templates: {target_dir}")
    else:
        # Create project directory
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"INFO: Created new Unirtos project directory: {target_dir}")

    # Reuse init logic
    print(f"INFO: Initializing project with Unirtos templates...")
    init_args = argparse.Namespace(project_dir=str(target_dir))
    handle_init(init_args)

    # Post-creation guidance
    print(f"\nSUCCESS: Unirtos project '{project_name}' created successfully!")
    print(f"GUIDANCE:")
    print(f"  1. Navigate to project directory: cd {project_name}")
    print(f"  2. Execute environment configuration: unirtos-cli env_setup")
    print(f"  3. For production use: Validate all critical files before deployment")

def handle_env_setup(args: argparse.Namespace) -> None:
    """
    Environment configuration execution command.
    Executes the Unirtos environment setup script with validated Python interpreter.
    
    Args:
        args: Parsed command-line arguments (contains project_dir)
    
    Raises:
        RuntimeError: If setup script/configuration is missing or execution fails
    """
    # Resolve target directory
    project_dir = Path(args.project_dir).absolute() if args.project_dir else Path.cwd()
    setup_script = project_dir / SETUP_SCRIPT_NAME
    config_file = project_dir / CONFIG_FILE_NAME

    # Validate prerequisite files
    if not setup_script.exists():
        raise RuntimeError(f"ERROR: Setup script not found: {setup_script}\nRun 'unirtos-cli init' first.")
    if not config_file.exists():
        raise RuntimeError(f"ERROR: Configuration file not found: {config_file}\nRun 'unirtos-cli init' first.")

    # Get validated Python command
    python_cmd = get_python_cmd()
    print(f"INFO: Executing Unirtos environment setup (Python: {python_cmd})")
    print(f"INFO: Setup script: {setup_script}")
    print(f"INFO: Configuration file: {config_file}")

    # Execute setup script
    cmd = [python_cmd, str(setup_script), "--config", str(config_file)]
    try:
        result = subprocess.run(
            cmd,
            cwd=project_dir,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8"
        )
        print(f"\nSUCCESS: Environment configuration executed successfully!")
        print(f"Setup Output:\n{result.stdout}")
    
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ERROR: Setup script failed:\n{e.stdout}") from e

def handle_version(args: argparse.Namespace) -> None:
    """
    Version information command.
    Supports both installed (PyPI) and development versions.
    
    Args:
        args: Parsed command-line arguments (unused for version command)
    """
    if get_pkg_version is not None:
        try:
            pkg_version = get_pkg_version(PACKAGE_NAME)
            print(f"{PACKAGE_NAME} v{pkg_version}")
            return
        except PackageNotFoundError:
            print(f"{PACKAGE_NAME} v{DEV_VERSION} (Development Build)")
        except Exception as e:
            print(f"{PACKAGE_NAME} v{DEV_VERSION} (Version Detection Failed: {str(e)[:50]})")
    else:
        # Legacy Python version fallback
        print(f"{PACKAGE_NAME} v{DEV_VERSION} (Legacy Python: {sys.version.split()[0]})")

# ===================== Command Line Interface =====================
def build_arg_parser() -> argparse.ArgumentParser:
    """
    Build command-line argument parser.
    Compliant with POSIX standards and Unirtos user experience.
    
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
     unirtos-cli env_setup -d /path/to/project
  4. Check version:
     unirtos-cli version
        """
    )

    # Subcommand parser
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
        "env_setup",
        help="Execute Unirtos environment configuration script (post-initialization)"
    )
    parser_env_setup.add_argument(
        "-d", "--project_dir",
        default=".",
        help="Project directory (default: current working directory)"
    )

    # Subcommand: version (version information)
    parser_version = subparsers.add_parser(
        "version",
        help="Display Unirtos CLI version"
    )

    return parser

# ===================== Main Entry Point =====================
def main() -> None:
    """
    Main entry point for Unirtos CLI.
    Implements robust error handling and user feedback for enterprise environments.
    """
    try:
        # Parse command-line arguments (POSIX-compliant)
        parser = build_arg_parser()
        args = parser.parse_args()

        # Route to appropriate command handler
        command_handlers = {
            "new": handle_new_project,
            "init": handle_init,
            "env_setup": handle_env_setup,
            "version": handle_version
        }

        if args.command in command_handlers:
            command_handlers[args.command](args)
        else:
            parser.print_help()

    # Error handling
    except RuntimeError as e:
        print(f"\nERROR: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nWARNING: Operation interrupted by user - Unirtos initialization aborted.")
        sys.exit(0)
    except Exception as e:
        print(f"\nCRITICAL ERROR: Unirtos CLI execution failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
