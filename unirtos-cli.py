#! /usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import os
import sys
import subprocess
import shutil
from pathlib import Path
import platform

# ===================== 模板路径处理（关键：适配EXE打包） =====================
def get_tmpl_dir():
    """
    获取模板文件夹路径：
    - 普通运行：脚本同目录的 app-tmpl 文件夹
    - EXE运行：打包时嵌入的 app-tmpl 资源目录
    """
    if getattr(sys, 'frozen', False):
        # EXE打包后，资源文件会放在 sys._MEIPASS 目录
        base_dir = Path(sys._MEIPASS)
    else:
        # 普通Python运行，模板文件夹在脚本同目录
        base_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    tmpl_dir = base_dir / "app-tmpl"
    
    if not tmpl_dir.exists():
        raise RuntimeError(f"❌ 模板文件夹不存在：{tmpl_dir}\n请确认 app-tmpl 与脚本/EXE在同一目录！")
    return tmpl_dir

# ===================== 工具函数 =====================
def is_dir_empty(dir_path):
    """检查目录是否为空（排除.和..）"""
    dir_path = Path(dir_path)
    if not dir_path.exists():
        return True
    return len([f for f in dir_path.iterdir() if not f.name.startswith('.')]) == 0

def get_python_cmd():
    """获取跨平台的python命令（统一用python）"""
    return "python"

def copy_tmpl_to_target(tmpl_dir, target_dir):
    """将模板文件夹内容拷贝到目标目录"""
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    # 递归拷贝模板文件夹所有内容（覆盖空文件，保留已存在文件）
    for item in tmpl_dir.iterdir():
        dest = target_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            # 仅拷贝不存在的文件（避免覆盖用户已修改的文件）
            if not dest.exists():
                shutil.copy2(item, dest)

    print(f"✅ 已从模板拷贝文件到：{target_dir}")
    print("📁 拷贝的文件列表：")
    for root, dirs, files in os.walk(target_dir):
        level = root.replace(str(target_dir), '').count(os.sep)
        indent = '  ' * level
        print(f'{indent}{os.path.basename(root)}/')
        sub_indent = '  ' * (level + 1)
        for f in files:
            print(f'{sub_indent}{f}')

# ===================== 命令处理函数 =====================
def handle_new(args):
    """处理 new <app> 命令：创建应用文件夹并拷贝模板文件"""
    app_name = args.app
    app_dir = Path(app_name).absolute()

    # 检查文件夹是否已存在
    if app_dir.exists():
        print(f"❌ 错误：应用文件夹 '{app_dir}' 已存在！")
        sys.exit(1)

    # 获取模板目录
    tmpl_dir = get_tmpl_dir()

    # 拷贝模板到新应用目录
    copy_tmpl_to_target(tmpl_dir, app_dir)
    print(f"\n🎉 应用 {app_name} 创建完成！")
    print(f"💡 后续操作：cd {app_name} && {get_python_cmd()} unirtos-cli env_setup")

def handle_init(args):
    """处理 init 命令：在当前空目录拷贝模板文件"""
    current_dir = Path.cwd()

    # 检查当前目录是否为空
    if not is_dir_empty(current_dir):
        print(f"❌ 错误：当前目录 '{current_dir}' 非空，无法执行init命令！")
        sys.exit(1)

    # 获取模板目录
    tmpl_dir = get_tmpl_dir()

    # 拷贝模板到当前目录
    copy_tmpl_to_target(tmpl_dir, current_dir)
    print(f"\n🎉 当前目录初始化完成！")
    print(f"💡 后续操作：{get_python_cmd()} unirtos-cli.exe env_setup")

def handle_env_setup(args):
    """处理 env_setup 命令：调用 unirtos_env_setup.py --config env_config.json"""
    current_dir = Path.cwd()
    setup_script = current_dir / "unirtos_env_setup.py"
    config_file = current_dir / "env_config.json"

    # 检查文件是否存在
    if not setup_script.exists():
        print(f"❌ 错误：未找到 {setup_script}，请先执行 unirtos-cli new/init 初始化应用！")
        sys.exit(1)
    if not config_file.exists():
        print(f"❌ 错误：未找到 {config_file}，请先执行 unirtos-cli new/init 初始化应用！")
        sys.exit(1)

    # 执行环境初始化脚本
    python_cmd = get_python_cmd()
    cmd = f"{python_cmd} {setup_script} --config {config_file}"
    print(f"📝 执行环境初始化命令：{cmd}")

    try:
        subprocess.run(cmd, shell=True, check=True)
        print("✅ 环境初始化命令执行完成！")
    except subprocess.CalledProcessError as e:
        print(f"❌ 环境初始化命令执行失败：{e}")
        sys.exit(1)

# ===================== 主函数 =====================
def main():
    # 创建参数解析器
    parser = argparse.ArgumentParser(description="Unirtos 应用开发CLI工具（模板拷贝版）")
    subparsers = parser.add_subparsers(dest="command", required=True, help="子命令：new/init/env_setup")

    # 1. new 子命令：创建新应用
    parser_new = subparsers.add_parser("new", help="创建新的Unirtos应用（格式：unirtos-cli new <app_name>）")
    parser_new.add_argument("app", help="应用名称（会创建对应名称的文件夹）")
    parser_new.set_defaults(handler=handle_new)

    # 2. init 子命令：初始化当前目录为Unirtos应用
    parser_init = subparsers.add_parser("init", help="在当前空目录初始化Unirtos应用")
    parser_init.set_defaults(handler=handle_init)

    # 3. env_setup 子命令：执行环境初始化
    parser_env_setup = subparsers.add_parser("env_setup", help="初始化Unirtos环境（需先有env_config.json和unirtos_env_setup.py）")
    parser_env_setup.set_defaults(handler=handle_env_setup)

    # 解析参数并执行对应处理函数
    args = parser.parse_args()
    args.handler(args)

if __name__ == "__main__":
    main()
