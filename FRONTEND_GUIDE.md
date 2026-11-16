# 鲁遗校真前端使用与部署指南

本文介绍 `frontend/` 的主要功能、在 VS Code 中运行开发版、构建静态发布包及当前运行边界。本文仅说明前端；后端安装和 API 约定请分别阅读根目录 `README.md` 与 `docs/API_CONTRACT.md`。

## 1. 当前版本能做什么

前端是 Vue 3 + Vite 工作台，包含以下界面和操作：

- 载入三个内置演示案例：典型案例、资料冲突案例、资料较少案例。
- 填写非遗资料、传播需求，并选择目标平台。目前小红书选项可用；微信公众号和抖音口播在页面中标记为后续支持。
- 查看分段文案、核验状态、原文引用和待核验提示。
- 打开来源抽屉查看引用，使用待核验栏及核验报告查看需要人工判断的项目。
- 在右侧文件栏编辑文案、保存草稿、查看修改记录，并导出文案或核验材料。
- 通过页面左下角的“切换”在示例数据模式和后端模式之间切换。

## 2. 运行模式与重要限制

### 示例数据模式

适合不启动后端时查看界面、演示内置案例和试用页面操作。模式使用前端内置的三份案例及浏览器内存中的临时草稿。

- 示例案例可直接使用；自定义输入只有能匹配内置案例关键词时才有预置生成结果。
- 草稿只保存在当前页面运行期间的内存中。刷新或关闭页面后，示例草稿不会保留。
- 示例模式的依据和状态是演示数据，不代表真实 AI 核验结果。
- 断开后端时，纯文本 `.txt`、`.md`、`.csv`、`.tsv`、`.json` 文件可由浏览器读取；`.docx` 需要后端解析，不适用于纯前端离线模式。

### 后端模式

前端原有 API 层使用 `/api/generate`、`/api/drafts`、`/api/extract` 等路径和旧版数据字段。当前协作仓库 C 后端的 `docs/API_CONTRACT.md` 使用另一套接口与字段。因此，**当前前端尚未适配仓库内的 C 后端，不能把后端模式当作已联通的部署方式**。前后端字段适配完成前，请使用示例数据模式；后端联调需另行完成并验证。

## 3. 准备环境

安装 Git、Node.js 22 LTS（含 npm）和 VS Code。克隆仓库后，在 VS Code 选择“终端 → 新建终端”，并确认终端使用 PowerShell。

从仓库根目录启动前端：

```powershell
Set-Location "F:\code\AI-Damoxing-Chuangxin-Chuanbo-Dasai\frontend"
npm ci
$env:VITE_USE_MOCK = "true"
npm run dev
```

在浏览器打开终端输出的地址，默认是 <http://127.0.0.1:5173>。保持终端运行；按 `Ctrl+C` 停止开发服务器。

`frontend/.npmrc` 将 npm 缓存放在项目内的 `.npm-cache/`。首次运行的依赖下载需要网络；`node_modules/`、缓存和构建目录均不应提交到 Git。

## 4. 页面操作步骤

1. 打开页面后，在“示例案例”区域选择典型、冲突或资料较少案例；也可以粘贴资料文本。
2. 填写传播需求，选择当前可用的平台。
3. 点击“生成文案并核对依据”。示例模式只对内置案例提供预置结果；无匹配案例时页面会提示无法生成。
4. 查看正文中的状态标记。点击引用标记可查看对应资料原文；使用待核验栏或核验报告逐项检查。
5. 要修改文案时，在右侧文件栏打开“文案正文”，进入编辑模式逐段修改，然后保存草稿。带有未保存改动时，导出前先按提示保存。
6. 从“导出”选择文案、文案加核验说明或核验报告。示例模式生成的文件来自当前页面的本地演示数据。
7. 页面左下角可切换模式。切换到后端模式之前，先确认后端接口与当前前端 API 兼容；目前该仓库的 C 后端尚未完成这项适配。

## 5. 构建与部署

在 PowerShell 中为静态示例模式构建：

```powershell
Set-Location "F:\code\AI-Damoxing-Chuangxin-Chuanbo-Dasai\frontend"
npm ci
$env:VITE_USE_MOCK = "true"
npm run build
```

构建输出位于 `frontend/dist/`。本地检查构建结果：

```powershell
npm run preview -- --host 127.0.0.1
```

浏览器打开 preview 命令输出的地址。preview 仅用于本机检查，不是生产服务器。

发布静态示例版时，将 `frontend/dist/` 的内容部署到静态网站托管服务，并配置默认首页为 `index.html`。因为该模式不依赖后端 API，纯前端演示不需要配置后端地址或 CORS。示例草稿仍只存在于当前页面内存中，不会成为多人共享或持久化数据。

若要部署完整前后端应用，必须先完成前端 API 对接，并安排可访问的后端服务、生产级 Web 服务器/反向代理、HTTPS、草稿数据库持久化与访问控制。当前 C 后端面向本地联调且无用户鉴权，不要直接暴露到公网。完成对接后，开发服务器的 `/api` 代理默认指向 `http://127.0.0.1:8000`，可用 `VITE_PROXY_TARGET` 配置其他开发后端地址；部署域名还需按后端要求配置精确的 `CORS_ORIGINS`。

## 6. 常用命令

```powershell
# 在 frontend 目录安装锁文件指定的依赖
npm ci

# 启动开发服务器
$env:VITE_USE_MOCK = "true"
npm run dev

# 构建静态发布目录
$env:VITE_USE_MOCK = "true"
npm run build

# 本地预览构建产物
npm run preview -- --host 127.0.0.1
```

如果要改用后端模式，不要设置 `VITE_USE_MOCK=true`，并先确认前后端 API 已兼容。PowerShell 关闭后，环境变量设置会随当前终端结束。

## 7. Git 提交注意事项

前端开发分支为远程 `feature/a-frontend`。提交前检查：

```powershell
git status --short
git diff --check
```

提交前端源码、`package.json`、`package-lock.json`、Vite 配置和必要说明即可。不要提交 `frontend/node_modules/`、`frontend/dist/`、`frontend/.npm-cache/`、`frontend/.tmp/`、根目录 `.cache/`、`.venv/`、SQLite 数据库或个人草稿。
