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

# 禁用SSL证书验证，解决GitHub资源下载时的证书校验问题
ssl._create_default_https_context = ssl._create_unverified_context

# ===================== 命令行参数解析模块 =====================
def parse_args():
    """
    解析命令行入参，指定环境初始化所需的JSON配置文件路径
    
    Returns:
        argparse.Namespace: 解析后的命令行参数对象，包含config参数
    """
    parser = argparse.ArgumentParser(description="Unirtos 环境初始化通用脚本")
    parser.add_argument("-c", "--config", required=True, help="JSON配置文件路径")
    return parser.parse_args()

# ===================== 基础工具函数模块 =====================
def get_os_type():
    """
    获取当前操作系统类型
    
    Returns:
        str: 操作系统类型（Linux/Windows）
    
    Raises:
        RuntimeError: 不支持的操作系统类型
    """
    sys_platform = platform.system()
    if sys_platform == "Linux":
        return "Linux"
    elif sys_platform == "Windows":
        return "Windows"
    else:
        raise RuntimeError(f"不支持的系统：{sys_platform}")

def get_unirtos_root(config):
    """
    获取Unirtos根目录路径（优先使用配置文件指定路径，无则使用默认路径）
    
    Args:
        config (dict): 环境配置字典
    
    Returns:
        Path: Unirtos根目录路径对象
    """
    if config.get("unirtos_root") and config["unirtos_root"].strip():
        return Path(config["unirtos_root"]).expanduser().absolute()
    return Path.home() / ".unirtos"

def run_command(cmd, cwd=None, check=True):
    """
    跨平台执行Shell命令
    
    Args:
        cmd (str): 待执行的命令字符串
        cwd (Path, optional): 命令执行的工作目录，默认None
        check (bool, optional): 是否检查命令执行结果，默认True
    
    Returns:
        str: 命令执行的标准输出内容
    
    Raises:
        CalledProcessError: 命令执行失败时抛出异常（包含错误信息）
    """
    if get_os_type() == "Windows" and "repo" in cmd:
        cmd = f"bash -c \"{cmd}\""
    
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
        print(f"命令执行失败：{cmd}")
        print(f"错误信息：{e.stderr}")
        raise

def check_repo_installed():
    """
    检测系统是否已安装repo工具
    
    Raises:
        RuntimeError: 未检测到repo工具时抛出异常（包含安装指引）
    """
    try:
        run_command("repo --version", check=True)
        print("repo工具已安装")
    except:
        raise RuntimeError("未检测到repo工具，请先安装（参考：https://gerrit.googlesource.com/git-repo/）")

def load_config(config_path):
    """
    加载JSON格式的环境配置文件
    
    Args:
        config_path (str): 配置文件路径
    
    Returns:
        dict: 解析后的配置字典
    
    Raises:
        RuntimeError: 配置文件不存在时抛出异常
    """
    config_path = Path(config_path).absolute()
    if not config_path.exists():
        raise RuntimeError(f"配置文件不存在：{config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    print(f"成功加载配置文件：{config_path}")
    return config

# ===================== SDK 处理函数模块 =====================
def check_sdk_version(config):
    """
    检测指定版本的SDK是否已存在且版本匹配
    
    Args:
        config (dict): 环境配置字典
    
    Returns:
        bool: SDK存在且版本匹配返回True，否则返回False
    """
    unirtos_root = get_unirtos_root(config)
    sdk_version = config["sdk"]["version"]
    sdk_dir = unirtos_root / "sdk" / f"v{sdk_version}"
    version_file = sdk_dir / "version.txt"
    
    if version_file.exists():
        with open(version_file, "r") as f:
            current_version = f.read().strip()
        if current_version == sdk_version:
            print(f"SDK v{sdk_version} 已存在且版本匹配")
            return True
    print(f"SDK v{sdk_version} 缺失/版本不匹配，开始拉取...")
    return False

def pull_sdk(config):
    """
    拉取/更新指定版本的SDK（基于单Master分支+版本目录XML结构）
    
    Args:
        config (dict): 环境配置字典
    
    Raises:
        RuntimeError: 指定版本的Manifest XML文件不存在时抛出异常
    """
    unirtos_root = get_unirtos_root(config)
    sdk_config = config["sdk"]
    sdk_version = sdk_config["version"]
    sdk_manifest_url = sdk_config["manifest_repo_url"]
    
    # SDK Manifest根目录（存储整个Master仓库）
    sdk_manifest_root = unirtos_root / "sdk" / "manifests"
    # 具体版本XML目录
    sdk_manifest_dir = sdk_manifest_root / f"v{sdk_version}"
    # SDK代码存储目录
    sdk_code_dir = unirtos_root / "sdk" / f"v{sdk_version}"
    
    # 确保目录存在
    sdk_manifest_root.mkdir(parents=True, exist_ok=True)
    sdk_code_dir.mkdir(parents=True, exist_ok=True)
    
    # 克隆/更新Master分支
    if not (sdk_manifest_root / ".git").exists():
        print(f"克隆SDK Manifest仓库(Master)到：{sdk_manifest_root}")
        run_command(
            f"git clone {sdk_manifest_url} {sdk_manifest_root}",
            cwd=sdk_manifest_root.parent
        )
    else:
        print(f"更新SDK Manifest仓库(Master)到最新版本")
        run_command("git pull origin master", cwd=sdk_manifest_root)
    
    # 校验版本目录下的default.xml是否存在
    sdk_xml_path = sdk_manifest_dir / "default.xml"
    if not sdk_xml_path.exists():
        raise RuntimeError(f"SDK Manifest仓库Master分支中未找到：{sdk_xml_path}\n请检查是否创建v{sdk_version}目录并放入default.xml")
    
    # 初始化并同步SDK代码
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
    
    print(f"同步SDK v{sdk_version}源码...")
    run_command("repo sync -j4 --force-sync", cwd=sdk_code_dir)
    
    # 写入版本标识文件
    with open(sdk_code_dir / "version.txt", "w") as f:
        f.write(sdk_version)
    print(f"SDK v{sdk_version} 拉取完成")

# ===================== 库处理函数模块 =====================
def check_lib_version(lib_config, unirtos_root):
    """
    检测指定版本的依赖库是否已存在且版本匹配
    
    Args:
        lib_config (dict): 单个库的配置字典
        unirtos_root (Path): Unirtos根目录路径对象
    
    Returns:
        bool: 库存在且版本匹配返回True，否则返回False
    """
    lib_name = lib_config["name"]
    lib_version = lib_config["version"]
    lib_dir = unirtos_root / "libraries" / lib_name / f"v{lib_version}"
    version_file = lib_dir / "version.txt"
    
    if version_file.exists():
        with open(version_file, "r") as f:
            current_version = f.read().strip()
        if current_version == lib_version:
            print(f"{lib_name} v{lib_version} 已存在且版本匹配")
            return True
    print(f"{lib_name} v{lib_version} 缺失/版本不匹配，开始拉取...")
    return False

def pull_lib(lib_config, unirtos_root):
    """
    拉取/更新指定版本的依赖库（基于单Master分支+组件-版本目录XML结构）
    
    Args:
        lib_config (dict): 单个库的配置字典
        unirtos_root (Path): Unirtos根目录路径对象
    
    Raises:
        RuntimeError: 指定版本的库Manifest XML文件不存在时抛出异常
    """
    lib_name = lib_config["name"]
    lib_version = lib_config["version"]
    lib_manifest_url = lib_config["manifest_repo_url"]
    
    # 组件Manifest根目录（存储整个Master仓库）
    lib_manifest_root = unirtos_root / "libraries" / "manifests"
    # 组件-版本XML目录
    lib_manifest_dir = lib_manifest_root / lib_name / f"v{lib_version}"
    # 库代码存储目录
    lib_code_dir = unirtos_root / "libraries" / lib_name / f"v{lib_version}"
    
    # 确保目录存在
    lib_manifest_root.mkdir(parents=True, exist_ok=True)
    lib_code_dir.mkdir(parents=True, exist_ok=True)
    
    # 克隆/更新Master分支
    if not (lib_manifest_root / ".git").exists():
        print(f"克隆组件Manifest仓库(Master)到：{lib_manifest_root}")
        run_command(
            f"git clone {lib_manifest_url} {lib_manifest_root}",
            cwd=lib_manifest_root.parent
        )
    else:
        print(f"更新组件Manifest仓库(Master)到最新版本")
        run_command("git pull origin master", cwd=lib_manifest_root)
    
    # 校验组件-版本目录下的default.xml是否存在
    lib_xml_path = lib_manifest_dir / "default.xml"
    if not lib_xml_path.exists():
        raise RuntimeError(f"组件Manifest仓库Master分支中未找到：{lib_xml_path}\n请检查是否创建{lib_name}/{lib_version}目录并放入default.xml")
    
    # 初始化并同步库代码
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
    
    print(f"同步{lib_name} v{lib_version}源码...")
    run_command("repo sync -j4 --force-sync", cwd=lib_code_dir)
    
    # 写入版本标识文件
    with open(lib_code_dir / "version.txt", "w") as f:
        f.write(lib_version)
    print(f"{lib_name} v{lib_version} 拉取完成")

def batch_process_libraries(config):
    """
    批量处理配置文件中声明的所有依赖库（检测版本+拉取/更新）
    
    Args:
        config (dict): 环境配置字典
    """
    unirtos_root = get_unirtos_root(config)
    for lib_config in config["libraries"]:
        print(f"\n--- 处理库：{lib_config['name']} v{lib_config['version']} ---")
        if not check_lib_version(lib_config, unirtos_root):
            pull_lib(lib_config, unirtos_root)

# ===================== 主流程模块 =====================
def main():
    """
    Unirtos环境初始化主流程（本地应用版）
    流程说明：
    1. 解析命令行参数并加载配置文件
    2. 前置检测（repo工具）
    3. 检测/拉取指定版本SDK
    4. 批量处理依赖库
    5. 输出环境初始化结果信息
    """
    try:
        # 解析命令行参数 + 加载配置
        args = parse_args()
        config = load_config(args.config)
        unirtos_root = get_unirtos_root(config)
        print(f"Unirtos 公共存储目录：{unirtos_root}")
        
        # 前置检测
        check_repo_installed()
        
        # 处理SDK
        print("\n===== 步骤1：检测/拉取SDK =====")
        if not check_sdk_version(config):
            pull_sdk(config)
        
        # 批量处理库
        print("\n===== 步骤3：批量处理依赖库 =====")
        batch_process_libraries(config)
        
        # 输出最终环境信息
        print("\n===== 环境初始化完成！=====")
        sdk_version_dir = f"v{config['sdk']['version']}"
        print(f"SDK 路径：{unirtos_root / 'sdk' / sdk_version_dir}")
        print("依赖库路径：")
        for lib in config["libraries"]:
            lib_version_dir = f"v{lib['version']}"
            print(f"  - {lib['name']}: {unirtos_root / 'libraries' / lib['name'] / lib_version_dir}")
        print("\n提示：可在本地应用中直接引用上述路径构建项目")
    
    except Exception as e:
        print(f"\n环境初始化失败：{str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
