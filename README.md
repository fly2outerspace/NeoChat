# NeoChat

| NeoChat 是一个全栈项目，用于汇集验证个人关于REALTIME LLM CHAT的想法。

本项目竭尽所能来实现一件事：

**让任何想象的角色扮演场景实现，在任何切入点继续想象与创造。**

![对话](assets/sample.png)

## 特点 Features
玩家可以通过管理发言对象、参与者来控制多人对话，营造家庭聚餐，暗地里的密谋或是会议。

![多人对话](assets/multi-npc.png)

---
NeoChat基于一个可以自定义的虚拟时间线实现，鼓励NPC在一个动态的时间线上规划和记录自己的生活。

NPC自觉管理的日程和人际关系

![管理日程和人际关系](assets/memory_relations.png)

角色记忆
![长期记忆](assets/memory.png)

角色关系网
![长期记忆](assets/relation.png)

模拟远程对话
![远程对话](assets/remotechat.png)

管理存档

![管理存档](assets/manage_saving.png)

编辑众多角色并保存

![角色卡编辑](assets/manage_npcs.png)

设置你的代理人，让它代替你自动说话

![用户设置](assets/set_your_agent.png)

配置你的模型

![配置模型](assets/modelsetting.png)

## 开始游玩

### 下载发布版本

前往 [Releases 页面](https://github.com/fly2outerspace/NeoChat/releases) 下载最新版本

### 启动程序

双击 `NeoChat.exe` 即可启动！

程序启动后，打开浏览器访问 **http://localhost:8000** 进入聊天界面。

前往模型配置界面，配置模型

设置你的第一个角色提示词，然后就可以开始聊天！

## 开发环境设置 (For Developers)

### 前置要求

- Python 3.8+
- Node.js 18+ (用于前端开发)
- npm 或 pnpm (推荐使用 pnpm)

### 1. 安装 Python 依赖

在项目根目录下执行：

```bash
pip install -r requirements.txt
```

### 2. 安装前端依赖

进入前端目录并安装依赖：

```bash
cd frontend/web-chat
npm install
# 或使用 pnpm
pnpm install
```

### 3. 安装 Meilisearch

Meilisearch 是一个开源的搜索引擎，用于消息检索功能。

#### 下载 Meilisearch

访问 Meilisearch 官方下载页面：
- **下载地址**: https://www.meilisearch.com/download

选择 Windows 版本下载 `meilisearch-windows-amd64.exe`

#### 配置 Meilisearch

1. 将下载的 `meilisearch-windows-amd64.exe` 放置到任意目录（例如：`E:\WorkSpace\Service\meilisearch\`）

2. 编辑 `config/config.toml` 文件，配置 Meilisearch 路径：

```toml
[meilisearch]
executable_path = "E:\\WorkSpace\\Service\\meilisearch\\meilisearch-windows-amd64.exe"
db_path = "E:\\WorkSpace\\Service\\meilisearch\\meili_data"
http_addr = "127.0.0.1:7700"
auto_start = true
```

> **提示**: 
> - `executable_path`: Meilisearch 可执行文件的完整路径
> - `db_path`: 数据持久化目录（可选）
> - `http_addr`: 服务地址，默认 `127.0.0.1:7700`
> - `auto_start`: 设置为 `true` 时，应用启动时会自动启动 Meilisearch

### 4. 启动开发服务器

#### 方式一：使用 Electron（推荐）

Electron 提供统一的进程管理，自动启动前端和后端：

```bash
cd electron
npm install  # 首次需要安装 Electron 依赖
npm run dev
```

**优势**：
- 一键启动前端和后端
- 统一的进程管理，优雅关闭
- 自动检测并复用已运行的前端 dev server
- 实时显示后端日志

#### 方式二：手动启动（传统方式）

**启动后端**：
```bash
python run_api.py
```

**启动前端**（新终端）：
```bash
cd frontend/web-chat
pnpm dev  # 或 npm run dev
```

**注意**：
- `run_api.py` 现在仅启动后端 API 服务器（端口 8000）
- 前端需要单独启动（端口 3000）
- 访问 http://localhost:3000 查看前端界面

#### 推荐开发流程

对于日常开发，推荐使用 Electron 方式：
- 更简洁：一个命令启动所有服务
- 更可靠：统一的进程管理，避免进程泄漏
- 更智能：自动检测已运行的服务并复用

对于调试或特殊需求，可以使用手动启动方式。