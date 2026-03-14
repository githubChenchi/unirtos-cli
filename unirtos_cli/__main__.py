#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unirtos CLI Tool (Cross-Platform: Windows/Linux/macOS)
Core Functionality: 
  - Create Unirtos application projects (new)
  - Initialize empty directories with Unirtos templates (init)
  - Execute environment configuration (env_setup)
  - Build Unirtos application (build)
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
DEV_VERSION = "0.1.3"

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
    print(f"  2. Execute environment configuration: unirtos-cli env_setup")
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
    Application build command.
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

    print(f"INFO: Starting Unirtos application build")
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
        
        print(f"\nSUCCESS: Unirtos application built successfully!")
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
     unirtos-cli env_setup -d /path/to/project
  4. Build application (default 4 parallel jobs):
     unirtos-cli build -d /path/to/project
  5. Build with custom parameters:
     unirtos-cli build --build-dir my-build --jobs 8
  6. Check version:
     unirtos-cli version
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
        "env_setup",
        help="Execute Unirtos environment configuration (post-initialization)"
    )
    parser_env_setup.add_argument(
        "-d", "--project_dir",
        default=".",
        help="Project directory (default: current working directory)"
    )

    # Subcommand: build (application compilation)
    parser_build = subparsers.add_parser(
        "build",
        help="Build Unirtos application (CMake + make compilation)"
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
            "env_setup": handle_env_setup,
            "build": handle_build,
            "version": handle_version
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
