# UniRTOS CLI 用户使用手册

**版本：** unirtos-cli v1.0.15+  
**适用平台：** Windows / Linux / macOS（目前编译工具链仅支持 Windows 系统）

---

## 1. 前提条件

在使用 unirtos-cli 之前，请确保以下工具已安装并配置到系统 `PATH`：

| 工具 | 说明 | 最低版本 |
|------|------|----------|
| **Python** | 运行 CLI 工具本身 | 3.9+ |
| **Git** | 拉取 SDK 与库源码 | 2.20+ |
| **unirtos 工具链** | 提供 `unirtos` 命令用于编译 | 1.0.5+ |

验证命令：

```bash
python --version    # 或 python3 --version
git --version
unirtos --version
```

---

## 2. 安装

```bash
pip install unirtos-cli
```

安装完成后，`unirtos-cli` 命令即可在终端中全局使用。

升级到最新版：

```bash
pip install --upgrade unirtos-cli
```

---

## 3. 快速开始

```bash
# 1. 创建并进入项目目录
unirtos-cli new unirtos-app
cd unirtos-app

# 2. 编辑 env_config.json（见第 4 节）

# 3. 拉取 SDK 与依赖库
unirtos-cli env-setup

# 4. 编译
unirtos-cli build
```

说明：`env-setup` 执行完成后，会在 App 根目录自动生成 `<app-name>.code-workspace`，可一键在 VSCode 打开 App、SDK 与依赖库代码。

编译产物默认输出到项目目录下的 `qos_build/release/<version>/`。

---

## 4. 配置文件详解 (env_config.json)

`env_config.json` 是项目根目录下的核心配置文件，由 `new` 命令自动生成模板，用户需在其中填写模块名称等信息。针对基于模板创建项目的场景，`sdk.version` 会自动写入最新可用 SDK 版本。

### 使用建议（推荐）

对于绝大多数用户，日常只需要关注并维护以下字段：

- `build.module`：编译模组型号
- `build.version`：目标版本号
- `build.jobs`：并发编译线程数
- `sdk.version`：SDK 版本
- `libraries.list[].name` / `libraries.list[].version`：依赖库名称与版本

### 切换 git 仓库镜像源

使用全局命令配置镜像源：

```bash
unirtos-cli git-mirror [<mirror>]
```

- `<mirror>` 可选值：`github`、`gitee`
- 省略 `<mirror>`：查询当前配置
- 若从未配置过：默认值为 `github`

### 完整示例

```json
{
  "unirtos_root": "",
  "build": {
    "module": "EG800ZCN_LA",
    "version": "EG800ZCNLAR01A01_BETA_OCPU_20260513",
    "jobs": 8
  },
  "sdk": {
    "version": "1.0.0"
  },
  "libraries": {
    "list": [
      {
        "name": "lib-name",
        "version": "2.0.0"
      }
    ]
  }
}
```

### 字段说明

#### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `unirtos_root` | string | 否 | UniRTOS 全局存储根目录的**绝对路径**。留空时自动使用默认路径：`~/.unirtos`（Linux/macOS）或 `C:\Users\<用户名>\.unirtos`（Windows）。 |

#### `build` 对象

控制 `unirtos-cli build` 的编译行为。所有字段均可被 CLI 参数覆盖。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `module` | string | **是** | SDK 模块/硬件平台名称，例如 `EG800ZCN_LA`。对应 `unirtos make --project` 参数。 |
| `version` | string | 否 | 固件版本字符串，例如 `EG800ZCNLAR01A01_BETA_OCPU_20260513`。留空时默认使用应用根目录名称。对应 `unirtos make --version` 参数。 |
| `jobs` | integer | 否 | 并行编译线程数。省略时默认为 `4`。可用 `-j` 参数临时覆盖。 |

#### `sdk` 对象

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `version` | string | **是** | 要使用的 SDK 版本号，例如 `1.0.0`。模板创建场景下会默认写入最新可用版本；`env-setup` 会将该值映射为 SDK Git 标签 `v<version>`（如 `v1.0.0`）进行源码检出并存储。 |

#### `libraries` 对象

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `list` | array | 否 | 依赖库列表。每项包含 `name`（库名）和 `version`（版本号）两个字段。不需要任何外部库时可省略 `list` 或置为空数组 `[]`。 |

##### 库列表项

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | **是** | 库名称，需与 Manifest 仓库中的目录名一致。 |
| `version` | string | **是** | 库版本号，例如 `2.0.0`。 |

---

## 5. 命令参考

### 5.1 `git-mirror` — 查询/设置全局镜像源

```bash
unirtos-cli git-mirror [<mirror>]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `mirror` | 省略 | 可选值：`github`、`gitee`。省略时查询当前镜像。 |

**示例：**

```bash
# 查询当前镜像
unirtos-cli git-mirror

# 切换到 gitee
unirtos-cli git-mirror gitee

# 切回 github
unirtos-cli git-mirror github
```

---

### 5.2 `new` — 创建新项目

创建一个新的项目。支持两种模式：

1. 模板模式（默认）：基于 `app-tmpl` 创建项目。
2. Demo 模式（`-r/--from-demo`）：基于远程同名 demo 仓库创建项目。

```bash
unirtos-cli new [-r] <project-name> [-v <version>] [-d <project-dir>] [-f]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `project-name` | 必填 | 项目名称（仅名称，不允许路径分隔符）。 |
| `-r`, `--from-demo` | 关闭 | 从远程 demo 创建项目。 |
| `-v`, `--version` | 省略 | 指定远程 demo 版本（支持 `1.0.0` 或 `v1.0.0`）。仅可与 `-r` 同时使用；省略时自动选择最新版本。 |
| `-d`, `--project-dir` | `.`（当前目录） | 项目基目录。最终目录为 `<project-dir>/<project-name>`。 |
| `-f`, `--force` | 关闭 | 强制更新 `<unirtos_root>/demos/manifests` 后再选 demo。仅可与 `-r` 同时使用。 |

**行为说明：**

- 模板模式（不带 `-r`）创建项目时，会自动将新项目 `env_config.json` 中的 `sdk.version` 写为最新可用 SDK 版本。

**示例：**

```bash
# 1) 基于模板创建（默认）
unirtos-cli new unirtos-app

# 2) 指定项目基目录
unirtos-cli new unirtos-app -d /path/to/workspace

# 3) 基于远程 demo 创建（按 demo 名称匹配）
unirtos-cli new -r demo_a

# 4) 基于远程 demo 创建（强制刷新本地缓存的 demo 列表信息）
unirtos-cli new -r demo_a -d /path/to/workspace -f

# 5) 基于远程 demo 指定版本创建
unirtos-cli new -r demo_a -v 1.0.0
```

---

### 5.3 `env-setup` — 拉取环境

根据 `env_config.json` 的配置，拉取指定版本的 SDK 和所有依赖库到本地存储目录。

```bash
unirtos-cli env-setup [-d <project-dir>]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-d`, `--project-dir` | `.`（当前目录） | 包含 `env_config.json` 的项目目录。 |

**示例：**

```bash
cd unirtos-app
unirtos-cli env-setup
```

---

### 5.4 `build` — 编译项目

调用 UniRTOS 工具链的 `unirtos make` 命令，以 **SDK 驱动** 模式编译当前外部应用。

```bash
unirtos-cli build [-d <project-dir>] [-j <jobs>] [-m <module>] [-v <version>]
```

| 参数                   | 默认值                     | 优先级                                            | 说明                             |
|-----------------------|---------------------------|--------------------------------------------------|---------------------------------|
| `-d`, `--project-dir` | `.`                       | —                                                | 项目目录。                         |
| `-j`, `--jobs`        | `4`                       | CLI > `env_config.build.jobs` > `4`              | 并行编译线程数。                    |
| `-m`, `--module`      | `env_config.build.module` | CLI > `env_config.build.module`                  | 模块名，例如 `EG800ZCN_LA`。        |
| `-v`, `--version`     | 应用根目录名称               | CLI > `env_config.build.version` > 应用根目录名称   | 固件版本字符串。                    |

**编译产物位置：**

```
<project-dir>/qos_build/release/<version>/
```

**示例：**

```bash
# 使用 env_config.json 中的默认配置编译
unirtos-cli build

# 指定模块和线程数（覆盖配置文件）
unirtos-cli build --module EG800ZCN_LA --jobs 8

# 指定完整版本字符串
unirtos-cli build -m EG800ZCN_LA -v EG800ZCNLAR01A01_BETA_OCPU_20260513
```

---

### 5.5 `clean` — 清理构建产物

删除项目目录下的所有编译产物（`qos_build/` 目录内容）。

```bash
unirtos-cli clean [-d <project-dir>]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-d`, `--project-dir` | `.` | 项目目录。 |

**示例：**

```bash
unirtos-cli clean
```

---

### 5.6 `menuconfig` — 打开配置菜单

内核功能开关配置界面。

```bash
unirtos-cli menuconfig [-d <project-dir>]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-d`, `--project-dir` | `.`（当前目录） | 起始目录（向上查找 `env_config.json` 所在目录）。 |

**示例：**

```bash
# 在当前项目目录执行
unirtos-cli menuconfig

# 指定项目目录执行
unirtos-cli menuconfig -d /path/to/project
```

---

### 5.7 `version` — 查看 CLI 版本

输出当前安装的 unirtos-cli 版本号。

```bash
unirtos-cli version
```

**示例输出：**

```
unirtos-cli v1.0.15
```

---

### 5.8 `ls-sdk` — 查看 SDK 版本列表

列出本地已安装或远程可用的 SDK 版本。

```bash
unirtos-cli ls-sdk [-r] [-f] [-j] [-d <project-dir>]
```

| 参数 | 说明 |
|------|------|
| `-l`, `--local` | 查看本地已安装版本（**默认行为**，可省略）。 |
| `-r`, `--remote` | 查看远程可用版本（从 Manifest 仓库读取）。 |
| `-f`, `--force` | 强制刷新本地 Manifest 仓库缓存（默认 1 小时内不重复拉取）。仅在 `-r` 时有效。 |
| `-j`, `--json-output` | 以 JSON 格式输出结果，便于脚本集成。 |
| `-d`, `--project-dir` | 起始目录。命令会从该目录向上查找 `env_config.json`；若找到则使用其中的 `unirtos_root`，否则回退到 `~/.unirtos`。默认为当前目录。 |

**示例：**

```bash
# 查看本地已安装的 SDK 版本
unirtos-cli ls-sdk
# 输出：
# Installed SDK versions:
#   - 1.0
#   - 1.1

# 查看远程可用的 SDK 版本（使用缓存）
unirtos-cli ls-sdk -r

# 强制刷新后查看远程版本
unirtos-cli ls-sdk -r -f

# 以 JSON 格式输出远程版本列表
unirtos-cli ls-sdk -r -j
# 输出：
# {
#   "success": true,
#   "message": "Remote SDK versions fetched successfully",
#   "type": "sdk-remote",
#   "data": ["1.0", "1.1", "1.2"]
# }
```

**缓存机制说明：** 远程版本查询会在本地缓存 Manifest 仓库（位于 `<unirtos_root>/sdk/manifests/`，若未命中应用配置则为 `~/.unirtos/sdk/manifests/`）。两次查询间隔不足 1 小时时自动使用缓存，不重复联网。使用 `-f` 可强制立即更新。

---

### 5.9 `ls-libs` — 查看库版本列表

列出本地已安装或远程可用的依赖库及其版本。

```bash
unirtos-cli ls-libs [-r] [-f] [-j] [-d <project-dir>]
```

参数与 `ls-sdk` 完全一致，含义相同。

`-d/--project-dir` 同样从该目录向上查找 `env_config.json`；若找到则使用其中的 `unirtos_root`，否则回退到 `~/.unirtos`。

**示例：**

```bash
# 查看本地已安装的库
unirtos-cli ls-libs
# 输出：
# Installed libraries:
#   component_a: 1.0.0, 2.0.0
#   component_b: 1.2.0

# 查看远程可用库及版本（JSON 格式）
unirtos-cli ls-libs -r -j
# 输出：
# {
#   "success": true,
#   "message": "Remote library versions fetched successfully",
#   "type": "lib-remote",
#   "data": {
#     "component_a": ["1.0.0", "2.0.0"],
#     "component_b": ["1.2.0"]
#   }
# }
```

---

### 5.10 `ls-demos` — 查看 Demo 版本列表

列出远程 Demo 及其版本。

```bash
unirtos-cli ls-demos [-f] [-j] [-d <project-dir>]
```

参数说明：

| 参数 | 说明 |
| --- | --- |
| `-f`, `--force` | 强制更新 `<unirtos_root>/demos/manifests`（忽略 1 小时更新间隔）。 |
| `-j`, `--json-output` | JSON 输出。 |
| `-d`, `--project-dir` | 起始目录。命令会从该目录向上查找 `env_config.json`；若找到则使用其中的 `unirtos_root`，否则回退到 `~/.unirtos`。 |

**示例：**

```bash
# 查看 demo 版本（默认读取本地 manifests 缓存；必要时按策略更新）
unirtos-cli ls-demos
# 输出：
# Remote demos:
#   demo_a: 1.0.0
#   demo_b: 2.0.0

# 强制更新 manifests 后输出 JSON
unirtos-cli ls-demos -f -j
# 输出：
# {
#   "success": true,
#   "message": "Demo versions fetched successfully",
#   "type": "demo-remote",
#   "data": {
#     "demo_a": ["1.0.0"],
#     "demo_b": ["2.0.0"]
#   }
# }
```

---

## 6. 基于模板的应用接入与编译配置

本节用于说明：执行 `new` 生成模板后，如何按需调整应用侧 `CMakeLists.txt`，确保应用可被 SDK 正确识别并完成编译。

### 6.1 `CMakeLists.txt` 最小接入要求

模板生成的 `CMakeLists.txt` 已满足外部应用编译契约，通常只需关注以下 2 点：

1. 将你的源码目录加入 `target_sources(...)`。
2. 将你的头文件目录加入 `target_include_directories(...)`。

最常见的自定义方式是扩展源码目录。例如新增 `components/` 目录后：

```cmake
file(GLOB_RECURSE APP_SRC
  ${CMAKE_CURRENT_SOURCE_DIR}/main/src/*.c
  ${CMAKE_CURRENT_SOURCE_DIR}/components/**/*.c
)

target_sources(${target} PRIVATE ${APP_SRC})

target_include_directories(${target} PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/main/inc
  ${CMAKE_CURRENT_SOURCE_DIR}/components
)
```

如果你新增的是子模块（子目录中也有 `CMakeLists.txt`），可以在顶层应用 `CMakeLists.txt` 中按需启用：

```cmake
add_subdirectory_if_exist(app_components)
```

### 6.2 推荐落地步骤

```bash
# 1) 初始化模板项目
unirtos-cli new unirtos-app
cd unirtos-app

# 2) 拉取环境
unirtos-cli env-setup

# 3) 按需配置 menuconfig
unirtos-cli menuconfig

# 4) 编写代码，并修改 CMakeLists.txt：补充你的源码/头文件路径

# 5) 编译验证
unirtos-cli build
```

### 6.3 常见失败原因

1. `CMakeLists.txt` 未将新增 `.c` 文件加入 `target_sources`，导致链接缺符号。
2. 头文件目录未加入 `target_include_directories`，导致编译找不到头文件。
3. 依赖的底层组件未通过 menuconfig 进行正确配置，导致相关 API 或组件不可用。

---

## 7. 本地存储目录结构

所有 SDK 与库源码统一存储在 `unirtos_root`（默认 `~/.unirtos/`）下，结构如下：

```
~/.unirtos/
├── sdk/
│   ├── manifests/              ← SDK Manifest Git 仓库（ls-sdk -r 与 env-setup 共享）
│   │   ├── .git/
│   │   ├── v1.0.0/
│   │   │   └── default.xml     ← v1.0.0 版本的 project 列表
│   │   └── v1.0.1/
│   │       └── default.xml
│   ├── v1.0.0/
│   │   ├── version.txt         ← 内容为 "1.0.0"，用于版本匹配校验
│   │   └── ...                 ← SDK 源码（由 manifest 定义的各 Git 仓库）
│   └── v1.0.1/
│       ├── version.txt
│       └── ...
├── demos/
│   ├── manifests/              ← Demo Manifest Git 仓库（ls-demos 与 new -r 共享）
│   ├── .git/
│   ├── demo_a/
│   │   └── v1.0.0/
│   │       └── default.xml
│   └── demo_b/
│       └── v2.0.0/
│           └── default.xml
└── libraries/
    ├── manifests/              ← 库 Manifest Git 仓库
    │   ├── .git/
    │   ├── component_a/
    │   │   ├── v1.0.0/
    │   │   │   └── default.xml
    │   │   └── v2.0.0/
    │   │       └── default.xml
    │   └── component_b/
    │       └── v1.2.0/
    │           └── default.xml
    ├── component_a/
    │   ├── v1.0.0/
    │   │   ├── version.txt     ← 内容为 "1.0.0"
    │   │   └── ...             ← 库源码
    │   └── v2.0.0/
    │       ├── version.txt
    │       └── ...
    └── component_b/
        └── v1.2.0/
            ├── version.txt
            └── ...
```

**版本增量管理：** 不同版本独立存储，互不覆盖。切换版本只需修改 `env_config.json` 中的版本号后重新执行 `env-setup`。

---

## 8. 典型工作流

### 场景一：新建项目并首次编译

```bash
# 第 1 步：创建项目
unirtos-cli new unirtos-app
cd unirtos-app

# 第 2 步：配置 env_config.json
# 必填：build.module、sdk.version
# 按需填写：build.version、build.jobs、libraries.list

# 第 3 步：拉取 SDK 和库（首次需联网）
unirtos-cli env-setup

# 第 4 步：编译
unirtos-cli build

# 编译产物在：./qos_build/release/<version>/
```

### 场景二：切换 SDK 版本

```bash
# 1. 修改 env_config.json 中的 sdk.version 为新版本，例如 "2.2.0"
# 2. 拉取新版本
unirtos-cli env-setup
# 3. 重新编译
unirtos-cli build
```

### 场景三：查询可用版本后添加依赖库

```bash
# 查看远端有哪些库可用
unirtos-cli ls-libs -r

# 查看某库的可用版本，在 JSON 中确认
unirtos-cli ls-libs -r -j

# 在 env_config.json 的 libraries.list 中添加：
# { "name": "component_b", "version": "1.2.0" }

# 重新执行 env-setup 拉取新库
unirtos-cli env-setup

# 重新编译（库会自动被 SDK CMake 集成进固件）
unirtos-cli build
```

### 场景四：基于远程 demo 创建项目

```bash
# 基于远程 demo（自动选择最新版本）创建项目
unirtos-cli new -r demo_a

# 基于远程 demo 指定版本创建项目
unirtos-cli new -r demo_a -v 1.0.0

# 进入新建目录（目录名自动带版本后缀）
cd demo_a-1.0.0

# 拉取 SDK 与依赖
unirtos-cli env-setup

# 编译
unirtos-cli build
```

说明：

1. `new -r` 会使用本地缓存的 `<unirtos_root>/demos/manifests`（必要时按策略更新）。
2. 目标目录固定为 `<project-name>-<version>`，即使未显式传 `-v` 也会自动拼接版本号。
3. 如需强制刷新 demo manifests，可加 `-f`：`unirtos-cli new -r demo_a -f`。

### 场景五：清理后重新编译

```bash
unirtos-cli clean
unirtos-cli build
```

---

## 9. 常见问题

### Q1：`env-setup` 时提示 "git not found"

**原因：** 系统未安装 Git 或 Git 不在 `PATH` 中。

**解决：** 安装 Git 并确保终端中 `git --version` 能正常输出，然后重新执行。

---

### Q2：`build` 时提示 `'unirtos' command not found`

**原因：** UniRTOS 交叉编译工具链未安装，或未添加到 `PATH`。

**解决：** 安装官方工具链包，按其说明将工具链目录添加到系统 `PATH`，重新打开终端后再执行编译。

---

### Q3：`build` 时提示 `SDK v2.1.0 not found`

**原因：** 尚未执行 `env-setup`，或 `sdk.version` 与已拉取的版本不一致。

**解决：**

```bash
unirtos-cli env-setup   # 拉取配置文件中指定的 SDK 版本
unirtos-cli build
```

---

### Q4：`env-setup` 后 `ls-sdk` 显示 SDK 版本未变化

**原因：** `ls-sdk` 默认显示**本地**版本（读取 `version.txt`），需使用 `-r` 查看远端可用版本。

```bash
unirtos-cli ls-sdk        # 本地已安装版本
unirtos-cli ls-sdk -r     # 远端可用版本
```

---

### Q5：远端版本列表不是最新的

**原因：** Manifest 仓库缓存未过期（默认 1 小时刷新一次）。

**解决：** 使用 `-f` 强制刷新：

```bash
unirtos-cli ls-sdk -r -f
unirtos-cli ls-libs -r -f
unirtos-cli ls-demos -f
```

---

### Q6：多个项目共用同一个 SDK，如何配置

`unirtos_root` 字段控制所有版本的统一存储位置，默认 `~/.unirtos`。多个项目可以在各自的 `env_config.json` 中留空（共享默认路径），不同版本会独立共存，互不干扰。如需隔离存储，填入不同路径即可：

```json
{
  "unirtos_root": "/opt/unirtos-workspace",
  ...
}
```

---

### Q7：如何在离线环境中使用

在联网机器上执行一次 `env-setup` 完成所有拉取后，将整个 `~/.unirtos/` 目录复制到离线机器的同路径下，然后 `env-setup` 会因版本匹配直接跳过拉取步骤，`build` 可正常使用。
