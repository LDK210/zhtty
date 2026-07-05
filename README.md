# HirePilot

AI 简历筛选 + 面试邀约 Agent。系统支持创建岗位 JD、批量上传 PDF/DOCX 简历、后台解析与评分、候选人排名、Agent 执行日志和面试邀约文案生成。

## 功能

- 创建招聘任务并录入岗位 JD。
- 上传多份 PDF/DOCX 简历，单文件最大 10MB。
- 使用 FastAPI `BackgroundTasks` 异步执行筛选，前端轮询状态、日志和结果。
- 使用 Pydantic 固定 `StructuredJD`、`StructuredCandidate`、`ScoreResult` 三类结构化输出。
- 后端校验评分维度，重新计算总分和推荐级别，不完全信任模型输出。
- 没有 `OPENAI_API_KEY` 时自动进入 Mock 模式，基于关键词稳定生成候选人、评分、问题和邀约。

## 技术栈

- Frontend: React + TypeScript + Vite + Tailwind CSS
- Backend: FastAPI + SQLAlchemy + Pydantic
- Database: PostgreSQL
- File parsing: pdfplumber / PyMuPDF / python-docx
- Deployment: Docker Compose + nginx

## 本地启动

Windows 一键启动：

```powershell
.\start.ps1
```

或使用批处理：

```bat
start.bat
```

脚本会按需创建 `backend/.venv`、安装后端依赖、安装前端依赖，并分别启动：

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

如果依赖已经安装完成，可以跳过安装步骤：

```powershell
.\start.ps1 -SkipInstall
```

关闭脚本打开的 PowerShell 窗口即可停止本地服务。

## 手动本地开发

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

前端：

```powershell
cd frontend
npm install
$env:VITE_API_BASE_URL="http://localhost:8000"
npm run dev
```

本地后端默认使用 SQLite `hirepilot.db`，启动时通过 `SQLAlchemy Base.metadata.create_all` 自动建表。MVP 暂不引入 Alembic，后续生产化再升级 migrations。

## Docker 启动

```powershell
docker compose up --build
```

浏览器打开：

```text
http://localhost:8080
```

Docker 环境中前端 nginx 会把 `/api` 代理到后端容器，避免手动配置跨域和 API 地址。

## 源码打包

生成可交付源码包：

```powershell
.\scripts\package-source.ps1
```

默认输出：

```text
hirepilot-source.zip
```

也可以指定输出路径：

```powershell
.\scripts\package-source.ps1 -OutputPath .\artifacts\hirepilot-source.zip
```

打包脚本会排除 `.git/`、`.codex/`、`.agents/`、`.venv/`、`node_modules/`、`dist/`、`uploads/`、数据库文件、日志文件和其他本地运行产物。

## AI 配置

默认无 Key 时自动 Mock：

```powershell
docker compose up --build
```

接入 OpenAI 兼容接口：

```powershell
$env:OPENAI_API_KEY="你的 Key"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
$env:OPENAI_MODEL="gpt-4o-mini"
docker compose up --build
```

DeepSeek、通义等兼容 OpenAI Chat Completions 的服务可通过 `OPENAI_BASE_URL` 和 `OPENAI_MODEL` 切换。

## API

- `POST /api/jobs` 创建招聘任务。
- `GET /api/jobs` 获取任务列表。
- `GET /api/jobs/{job_id}` 获取任务详情、整体状态、简历状态和进度统计。
- `POST /api/jobs/{job_id}/resumes` 批量上传简历。
- `POST /api/jobs/{job_id}/run` 启动后台筛选任务。
- `GET /api/jobs/{job_id}/results` 获取候选人排名。
- `GET /api/candidates/{candidate_id}` 获取候选人详情。
- `GET /api/jobs/{job_id}/logs` 获取 Agent 执行日志。

`/run` 校验规则：

- JD 为空返回 `400 Bad Request`。
- 没有任何已上传简历返回 `400 Bad Request`。
- `running` 或 `completed` 状态重复启动返回 `409 Conflict`。

## 状态规则

`jobs.status`：

- `draft`
- `ready`
- `running`
- `completed`
- `failed`

`resumes.status`：

- `uploaded`
- `extracting`
- `parsed`
- `scored`
- `completed`
- `failed`

后台任务结算：

- 全部简历成功：`job.status=completed`
- 部分简历失败、部分成功：`job.status=completed`
- 全部简历失败：`job.status=failed`

## Agent 工作流

1. 解析岗位 JD。
2. 提取简历文本。
3. 结构化候选人信息。
4. 多维评分并由后端兜底计算总分。
5. 生成面试问题和邀约文案。
6. 保存结果并写入 Agent 日志。
