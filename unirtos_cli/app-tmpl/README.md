# Hello World Demo

## 概述

Hello World Demo 是一个基于 UNIRTOS 的入门级示例项目。该项目演示了如何在 UNIRTOS 平台上创建、初始化和运行一个简单的任务。通过此示例，开发者可以快速了解 UNIRTOS 的基本开发流程和 API 使用方法。

**适用平台**：所有支持 UNIRTOS 的平台

## 快速上手

### 1. 开发环境搭建

参考 [UNIRTOS 快速入门](https://docs.quectel.com/zh/UniRTOS/UniRTOS%E6%96%87%E6%A1%A3/%E5%BF%AB%E9%80%9F%E4%B8%8A%E6%89%8B/%E5%BF%AB%E9%80%9F%E4%B8%8A%E6%89%8B.html) 文档，了解如何搭建开发环境,了解开发过程。

#### 2. 获取项目
进入unirtos/qos_applications目录下执行以下命令下载项目：
```bash
git clone https://github.com/UniRTOS/unirtos_helloworld_demos.git
```

#### 4. 项目结构

```
helloworld_demos/
├── CMakeLists.txt           # CMake 构建配置
├── demo.manifest.json       # 应用清单文件
├── README.md               # 本文件
├── hello_world.c           # 源代码
└── depend.config           # 依赖配置
```

#### 5. 构建项目
unirtos 目录下运行以下命令进行构建：
```bash
unirtos make EG800ZCN_LA EG800ZCNLAR01A01M04_BETA_OCPU_20260511
```

#### 6. 日志展示

成功运行后，您会在串口看到以下日志输出：

```
[V/DEMO] hello world count=0
[V/DEMO] hello world count=1
[V/DEMO] hello world count=2
[V/DEMO] hello world count=3
...
```

每行输出间隔约 1 秒。

## 代码概览

#### 示例工作流程

```
程序启动
    ↓
调用 unir_hello_world_init()
    ↓
创建名为 "unir_hello_world_demo" 的任务
    ↓
进入任务主函数 unir_hello_world_demo_process()
    ↓
无限循环：
  ├─ 输出当前计数值
  ├─ 睡眠 1 秒
  └─ 计数器 +1
```

#### 主要 API 接口

##### unir_hello_world_init
任务初始化函数
- 检查任务是否已创建
- 创建任务，设置堆栈大小和优先级
- 设置任务名称和入口函数

##### unir_hello_world_demo_process
任务处理函数
- 维护计数器
- 循环输出日志
- 定期睡眠

## 论坛社区

[点此进入](https://forumschinese.quectel.com/c/66-category/66)

## 贡献指南

欢迎提交 Issue 和 Pull Request！


