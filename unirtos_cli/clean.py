#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unirtos Clean Module
Core Functionality:
  - Remove all build artifacts from app directory (qos_build/)
  - Clean intermediate compilation products safely
Copyright (c) Chavis.Chen 2026. All Rights Reserved.
"""

import os
import sys
import shutil
from pathlib import Path


def clean_app_build_outputs() -> None:
    """
    Clean all build artifacts from current app directory.
    
    Removes:
    - qos_build/build (CMake intermediate files)
    - qos_build/gccout (gccout pre-requisite for app build)
    - qos_build/release (final firmware packages)
    - output (fallback output directory, if used)
    
    Raises:
        RuntimeError: If cleanup fails
    """
    app_root = Path(os.getcwd()).absolute()
    
    build_dirs = [
        app_root / "qos_build" / "build",
        app_root / "qos_build" / "gccout",
        app_root / "qos_build" / "release",
        app_root / "output",
    ]
    
    cleaned_count = 0
    for build_dir in build_dirs:
        if build_dir.exists():
            try:
                if build_dir.is_dir():
                    shutil.rmtree(build_dir)
                    print(f"[unirtos clean] removed: {build_dir.relative_to(app_root)}")
                    cleaned_count += 1
                else:
                    build_dir.unlink()
                    print(f"[unirtos clean] removed: {build_dir.relative_to(app_root)}")
                    cleaned_count += 1
            except Exception as e:
                raise RuntimeError(f"Failed to remove {build_dir}: {str(e)}")
    
    if cleaned_count == 0:
        print("[unirtos clean] no build artifacts found (already clean)")
    else:
        print(f"[unirtos clean] cleaned {cleaned_count} artifact(s)")


def main() -> None:
    """
    Main execution entry point for the Unirtos clean module.
    """
    try:
        clean_app_build_outputs()
    except KeyboardInterrupt:
        print("\nWARNING: Clean operation interrupted by user.")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\nERROR: Clean failed: {str(e)}", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"\nCRITICAL ERROR: Unexpected clean failure: {str(e)}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
