# 山东非遗文旅宣传内容核验与改写助手

本轮为 C 模块：FastAPI + SQLite 后端与模拟联调。无需 API 密钥，不调用外部模型。`mode=mock`，即使段落为 supported，也只表示模拟器提供了原文引用，不代表完成真实 AI 核验。A 的正式前端、B 的真实 AI 尚未接入。

## Windows PowerShell

在项目根目录运行（Python 3.10+）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

另开 PowerShell，在项目根目录运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

交互接口文档：<http://127.0.0.1:8000/docs>。默认数据库为项目根目录 `data/drafts.sqlite3`，启动自动建表，重启保留草稿。数据目录、虚拟环境、密钥文件已加入 `.gitignore`。可配置数据库路径：

```powershell
$env:DRAFT_DB_PATH = Join-Path $PWD 'data\local.sqlite3'
$env:CORS_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173'
```

在启动命令之前设置环境变量。前端 API base URL 使用 `http://127.0.0.1:8000`；更换前端端口时同步配置 CORS_ORIGINS（逗号分隔的精确 origin）。本服务面向本地联调，无用户鉴权，不应直接暴露到公网。

- A 接入：[API 合同与示例](docs/API_CONTRACT.md)。
- B 接入：[生成器替换说明](docs/GENERATOR_INTEGRATION.md)。
- 测试覆盖中文创建、引用、修改历史、原子保存、下载最新版、重建应用读回、空输入、404、稳定资料 ID 和生成器注入。

C v0.1 交付前已在独立目录的新虚拟环境中完成安装、5 项测试、真实 HTTP 联调和服务进程重启验收，详见 [交付复核记录](docs/DELIVERY_REVIEW.md)。交给队友时包含 `backend/` 的源码、依赖清单和测试，以及 `docs/`、`README.md`、`pytest.ini`、`.gitignore`；不要打包 `.venv/`、`data/`、`.acceptance-*/` 或缓存。示例 JSON 只用于前端开发，读取服务中的草稿必须使用本次创建返回的 draftId。
