#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unirtos Application Build Script (Commercial Edition)
Copyright (c) [Your Company Name] [Year]. All Rights Reserved.

Core Functionalities:
1. Automatically load environment configuration from env_config.json (fixed path)
2. Validate and pull required Unirtos SDK/libraries via unirtos_env_setup.py
3. Auto-download missing SDK/library versions before compilation
4. Pass SDK/library root directories (containing their CMakeLists.txt) to app CMake
5. Dynamically pass library name list to CMake (no hardcoding)
6. Execute CMake configuration and parallel make compilation
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path
import json

# Import core interfaces from unirtos_env_setup.py (same directory requirement)
try:
    import unirtos_env_setup as env
except ImportError:
    raise RuntimeError(
        "ERROR: unirtos_env_setup.py not found in current directory!\n"
        "Resolution: Ensure unirtos_env_setup.py exists in the same directory as build.py, "
        "or generate it via 'unirtos-cli init'."
    )

# ===================== Command Line Argument Parser =====================
def parse_build_args() -> argparse.Namespace:
    """
    Parse command line arguments for build script.
    Removes config file parameter to simplify user operation (fixed env_config.json).
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Unirtos Application Build Script (Commercial Edition)",
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
    Ensures configuration consistency with unirtos_env_setup.py.
    
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
    Resolve absolute paths for Unirtos SDK and libraries (root directories containing CMakeLists.txt).
    Validates component existence and triggers auto-download for missing versions.
    
    Args:
        config: Parsed Unirtos environment configuration dictionary
    
    Returns:
        dict: Component path mapping with keys:
              - unirtos_root: Root directory for all Unirtos components
              - sdk_path: Absolute path to target SDK version (contains SDK's CMakeLists.txt)
              - libs_path: Dictionary of library names to their root paths (each contains lib's CMakeLists.txt)
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
    
    # Validate SDK contains CMakeLists.txt
    if not (sdk_path / "CMakeLists.txt").exists():
        raise RuntimeError(f"ERROR: SDK v{sdk_version} missing CMakeLists.txt at {sdk_path}")
    print(f"INFO: SDK v{sdk_version} path (with CMakeLists.txt): {sdk_path}")

    # Resolve library paths (auto-download if missing)
    libs_path = {}
    for lib_config in config["libraries"]:
        lib_name = lib_config["name"]
        lib_version = lib_config["version"]
        lib_path = unirtos_root / "libraries" / lib_name / f"v{lib_version}"
        
        if not env.check_lib_version(lib_config, unirtos_root):
            print(f"INFO: {lib_name} v{lib_version} not found - initiating download...")
            env.pull_lib(lib_config, unirtos_root)
        
        # Validate library contains CMakeLists.txt
        if not (lib_path / "CMakeLists.txt").exists():
            raise RuntimeError(f"ERROR: {lib_name} v{lib_version} missing CMakeLists.txt at {lib_path}")
        
        libs_path[lib_name] = lib_path
        print(f"INFO: {lib_name} v{lib_version} path (with CMakeLists.txt): {lib_path}")

    return {
        "unirtos_root": unirtos_root,
        "sdk_path": sdk_path,
        "libs_path": libs_path
    }

# ===================== CMake Build Executor =====================
def run_cmake_build(config: dict, build_dir: str, jobs: int) -> None:
    """
    Execute CMake configuration and make compilation.
    Passes SDK/library root paths (with their CMakeLists.txt) to app CMake for import.
    
    Args:
        config: Parsed Unirtos environment configuration
        build_dir: Name of the CMake build directory
        jobs: Number of parallel jobs for make compilation
    
    Raises:
        RuntimeError: If CMake configuration or make compilation fails
    """
    # Resolve application and build directories
    app_root = Path(os.path.dirname(os.path.abspath(__file__))).absolute()
    build_dir_abs = app_root / build_dir
    cmake_list_path = app_root  # App's CMakeLists.txt located in application root

    # Get resolved component paths (SDK/lib roots with CMakeLists.txt)
    component_paths = get_unirtos_component_paths(config)
    sdk_path = component_paths["sdk_path"]
    libs_path = component_paths["libs_path"]

    # Construct CMake command with dynamic parameters (pass CMake script roots)
    cmake_args = [
        "cmake",
        f"-DUNIRTOS_SDK_ROOT={sdk_path}",  # SDK root (contains SDK's CMakeLists.txt)
        f"-DUNIRTOS_TOOLCHAIN_PREFIX={component_paths['unirtos_root'] / 'toolchain/arm-gcc/v12.2/bin/arm-none-eabi-'}",
        # Pass dynamic library list (pipe-separated to avoid CMake semicolon parsing issues)
        f'-DUNIRTOS_LIBS={"|".join(libs_path.keys())}',
        f"-S{cmake_list_path}",
        f"-B{build_dir_abs}"
    ]

    # Add library root paths to CMake arguments (each contains lib's CMakeLists.txt)
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
            "2. SDK/library missing CMakeLists.txt (check download completeness)\n"
            "3. Syntax errors in app's CMakeLists.txt"
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
            "2. Errors in SDK/library CMakeLists.txt\n"
            "3. App code incompatible with SDK/library APIs"
        )

    # Print build completion and output details
    print(f"\n✅ SUCCESS: Build completed successfully! Output directory: {build_dir_abs}")
    output_files = [f for f in build_dir_abs.iterdir() if f.suffix in [".bin", ".hex", ".elf", ".dis"]]
    
    if output_files:
        print("📦 Key Output Files:")
        for output_file in output_files:
            print(f"  - {output_file.name}")

# ===================== Main Execution Flow =====================
def main() -> None:
    """
    Main execution entry point for the Unirtos build script.
    Implements full build lifecycle: argument parsing → config loading → 
    dependency validation (SDK/lib CMakeLists.txt check) → CMake configuration → compilation.
    """
    # Print commercial header
    print("=========================================")
    print("  Unirtos Application Build Tool (v1.0)  ")
    print("=========================================")

    try:
        # Parse command line arguments
        args = parse_build_args()

        # Load environment configuration
        print("INFO: Loading environment configuration (env_config.json)...")
        config = load_unirtos_config()

        # Validate repo tool availability
        print("INFO: Validating repo tool integrity...")
        env.check_repo_installed()

        # Execute build process (with SDK/lib CMake validation)
        run_cmake_build(config, args.build_dir, args.jobs)

    except KeyboardInterrupt:
        print("\n⚠️ WARNING: Build process interrupted by user.")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n❌ ERROR: Build failed: {str(e)}", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: Unexpected build failure: {str(e)}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
