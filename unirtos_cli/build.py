#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unirtos Build Module
Core Functionality:
  - Resolve Unirtos component paths (SDK/libraries)
  - Execute CMake configuration and parallel compilation
  - Support cross-platform build process
Copyright (c) [Your Company Name] [Year]. All Rights Reserved.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import json

# Import package-internal environment setup module (关键修改：包内导入)
try:
    from unirtos_cli import unirtos_env_setup as env
except ImportError:
    # Fallback for development mode (本地调试)
    sys.path.append(str(Path(os.path.dirname(os.path.abspath(__file__))).parent))
    import unirtos_env_setup as env

# ===================== Command Line Argument Parser =====================
def parse_build_args() -> argparse.Namespace:
    """
    Parse command line arguments for build module.
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Unirtos Application Build Module",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-b", "--build-dir",
        default="build",
        help="CMake build directory (default: build/)"
    )
    parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=4,
        help="Number of parallel make jobs (default: 4, optimizes compilation speed)"
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

# ===================== Component Path Resolver =====================
def get_unirtos_component_paths(config: dict) -> dict:
    """
    Resolve absolute paths for Unirtos SDK and libraries.
    Validates component existence and triggers auto-download for missing versions.
    
    Args:
        config: Parsed Unirtos environment configuration dictionary
    
    Returns:
        dict: Component path mapping with keys:
              - unirtos_root: Root directory for all Unirtos components
              - sdk_path: Absolute path to target SDK version
              - libs_path: Dictionary of library names to their absolute paths
    """
    # Print version configuration for transparency
    print("\n===== Unirtos Version Configuration =====")
    print(f"SDK Version: {config['sdk']['version']}")
    for lib_config in config["libraries"]:
        print(f"{lib_config['name']} Version: {lib_config['version']}")
    print("=========================================\n")

    # Get Unirtos root directory
    unirtos_root = env.get_unirtos_root(config)
    print(f"INFO: Unirtos root directory: {unirtos_root}")

    # Resolve SDK path (auto-download if missing)
    sdk_version = config["sdk"]["version"]
    sdk_path = unirtos_root / "sdk" / f"v{sdk_version}"
    
    if not env.check_sdk_version(config):
        print(f"INFO: SDK v{sdk_version} not found - initiating download...")
        env.pull_sdk(config)
    
    print(f"INFO: SDK v{sdk_version} path: {sdk_path}")

    # Resolve library paths (auto-download if missing)
    libs_path = {}
    for lib_config in config["libraries"]:
        lib_name = lib_config["name"]
        lib_version = lib_config["version"]
        lib_path = unirtos_root / "libraries" / lib_name / f"v{lib_version}"
        
        if not env.check_lib_version(lib_config, unirtos_root):
            print(f"INFO: {lib_name} v{lib_version} not found - initiating download...")
            env.pull_lib(lib_config, unirtos_root)
        
        libs_path[lib_name] = lib_path
        print(f"INFO: {lib_name} v{lib_version} path: {lib_path}")

    return {
        "unirtos_root": unirtos_root,
        "sdk_path": sdk_path,
        "libs_path": libs_path
    }

# ===================== CMake Build Executor =====================
def run_cmake_build(config: dict, build_dir: str, jobs: int) -> None:
    """
    Execute CMake configuration and make compilation with dynamic component paths.
    Passes dynamic library list to CMake (supports arbitrary library names).
    
    Args:
        config: Parsed Unirtos environment configuration
        build_dir: Name of the CMake build directory
        jobs: Number of parallel jobs for make compilation
    
    Raises:
        RuntimeError: If CMake configuration or make compilation fails
    """
    # Resolve application and build directories
    app_root = Path(os.getcwd()).absolute()
    build_dir_abs = app_root / build_dir
    cmake_list_path = app_root

    # Get resolved component paths
    component_paths = get_unirtos_component_paths(config)
    sdk_path = component_paths["sdk_path"]
    libs_path = component_paths["libs_path"]

    # Construct CMake command with dynamic parameters
    cmake_args = [
        "cmake",
        f"-DUNIRTOS_SDK_ROOT={sdk_path}",
        f"-DUNIRTOS_TOOLCHAIN_PREFIX={component_paths['unirtos_root'] / 'toolchain/arm-gcc/v12.2/bin/arm-none-eabi-'}",
        # Pass dynamic library list (pipe-separated to avoid CMake semicolon parsing issues)
        f'-DUNIRTOS_LIBS={"|".join(libs_path.keys())}',
        f"-S{cmake_list_path}",
        f"-B{build_dir_abs}"
    ]

    # Add library paths to CMake arguments (generic handling for all libraries)
    for lib_name, lib_path in libs_path.items():
        lib_name_upper = lib_name.upper()
        cmake_args.append(f"-DUNIRTOS_LIB_{lib_name_upper}={lib_path}")

    # Create build directory if not exists
    build_dir_abs.mkdir(parents=True, exist_ok=True)
    
    # Execute CMake configuration
    print(f"\nINFO: Executing CMake command: {' '.join(cmake_args)}")
    try:
        subprocess.run(
            cmake_args,
            check=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError:
        raise RuntimeError(
            "CMake configuration failed.\n"
            "Common Causes:\n"
            "1. CMake is not installed (Install: sudo apt install cmake)\n"
            "2. SDK download incomplete or path invalid\n"
            "3. Syntax errors in CMakeLists.txt"
        )

    # Execute parallel make compilation
    make_args = ["make", f"-j{jobs}", f"-C{build_dir_abs}"]
    print(f"\nINFO: Executing make command: {' '.join(make_args)}")
    try:
        subprocess.run(
            make_args,
            check=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError:
        raise RuntimeError(
            "Make compilation failed.\n"
            "Common Causes:\n"
            "1. Toolchain not installed (e.g., arm-none-eabi-gcc)\n"
            "2. Source code syntax errors\n"
            "3. Missing dependencies in CMakeLists.txt"
        )

    # Print build completion and output details
    print(f"\nSUCCESS: Build completed successfully! Output directory: {build_dir_abs}")
    output_files = [f for f in build_dir_abs.iterdir() if f.suffix in [".bin", ".hex", ".elf", ".dis"]]
    
    if output_files:
        print("Key Output Files:")
        for output_file in output_files:
            print(f"  - {output_file.name}")

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

        # Validate repo tool availability
        print("INFO: Validating repo tool integrity...")
        env.check_repo_installed()

        # Execute build process
        run_cmake_build(config, args.build_dir, args.jobs)

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
