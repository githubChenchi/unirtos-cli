# unirtos-cli 构建指南

## 环境准备

```bash
sudo apt update
sudo apt install python3 python3-pip -y
pip3 install --upgrade build twine
```

## 构建分发包

```bash
python3 -m build
```

构建完成后，根目录会生成 dist/ 文件夹，包含：

- unirtos_cli-0.1.4.tar.gz（源码包）
- unirtos_cli-0.1.4-py3-none-any.whl（wheel 包，跨平台通用）

## 本地验证

### 安装 wheel 包
```bash
pip3 install --force-reinstall dist/unirtos_cli-0.1.4-py3-none-any.whl
```

### 验证 unirtos-cli 命令行工具
```bash
unirtos-cli version
```

## 上传到测试版 PyPI

### 上传分发包

> 先注册 PyPI 账号，并获取 API Token

```bash
twine upload --repository testpypi dist/*
```

### 安装 unirtos-cli

```bash
pip install -i https://test.pypi.org/simple/ --upgrade unirtos-cli
```

### 验证 unirtos-cli 命令行工具
```bash
unirtos-cli version
```