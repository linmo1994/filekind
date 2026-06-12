# filekind

按 **软件/系统项目名称**、**项目编号** 与 **内容关联度**，在本地整理文件。数据不出本机；无 SQLite；进程结束即释放内存中的模型实例。

## 特性

- 提取文档 **前 3 页**（或等价字符）用于分类，不做开放式问答
- **规则**（编号/系统名）→ **向量关联**（bge-small-zh）→ **可选本地 LLM**（Qwen2.5-1.5B GGUF）
- 分阶段加载模型，适配 **8GB 内存**
- 默认 **dry-run**，输出 `plan.json`；确认后 **复制**到 `已整理/`（**待整理原文件保留**）；可用 `rollback` 删除已整理副本

## 安装

```bash
cd filekind
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 可选：本地 LLM（8GB 推荐 Qwen2.5-1.5B Q4_K_M）
pip install -e ".[llm]"

# 可选：扫描件 OCR
pip install -e ".[ocr]"
```

## 配置

```bash
cp projects.example.yaml projects.yaml
```

编辑 `projects.yaml`：

- `paths.source` / `paths.dest`：与 `projects.yaml` **同目录** 下的 `待整理` / `已整理`（相对路径）
- **`paths.inventory_excel`**：**项目清单 Excel**（必填；填写**文件名**即可）。工具会在 `待整理/` 下**递归查找**同名文件，也会检查与 `projects.yaml` 同目录。读取清单后对**除该 Excel 以外**的文件分类；清单文件本身不会被移动
- `models.llm_gguf`：本地 GGUF 路径（留空则跳过 LLM，仅用规则+向量）
- `runtime.max_files_per_run`：单次上限（8GB 建议 500）

### 项目清单 Excel

1. 将清单文件（如 `国高资料清单2026 版型清单.xlsx`）放入 **`待整理/`**
2. 在 `projects.yaml` 中设置：

```yaml
paths:
  inventory_excel: "国高资料清单2026 版型清单.xlsx"
```

3. 表格应包含 **项目编号 / 项目名称** 等列；也支持每行出现类似 `202432--CSP311` 的代号（可与文件名前缀对应）
4. 进入 **`dist/filekind/`**，将文件放入 `待整理/`，运行 `filekind run` 或双击 **`双击可整理文件.command`**

命令行也可临时指定：

```bash
filekind run --inventory "国高资料清单2026 版型清单.xlsx" --apply --no-dry-run
```

## 使用

```bash
# 首次使用：复制并编辑配置（待整理/已整理 会在首次 run 时自动创建）
cp projects.example.yaml projects.yaml

# 校验配置
filekind validate-config

# 把文件放进 dist/filekind/待整理，然后生成计划（见下方打包说明）
filekind run

# 一键整理（复制到已整理，待整理原文件保留）
filekind run --apply --no-dry-run

# macOS 双击：在 dist/filekind/ 内双击 双击可整理文件.command（见下方说明）

# 临时指定其它目录（可选）
filekind run ~/Downloads/inbox ~/Organized

# 确认 plan.json 后复制到已整理（待整理原文件不动）
filekind apply filekind-work/<timestamp>/plan.json --no-dry-run

# 删除 manifest 中记录的已整理副本
filekind rollback filekind-work/<timestamp>/manifest.json --no-dry-run
```

### macOS 双击一键整理

先执行 `./scripts/build_executable.sh`，然后：

1. `cd dist/filekind`
2. 在 `projects.yaml` 中配置 **`paths.inventory_excel`**（项目清单 Excel 文件名）
3. 将 **清单 Excel** 与其余待整理文件一并放入 **`待整理/`**
4. 双击 **`双击可整理文件.command`**

脚本等价于 `filekind run --apply --no-dry-run`，并会自动：

- `xattr -dr com.apple.quarantine` 去除隔离标记  
- `codesign --sign -` 本地 ad-hoc 签名  
- 缺少 `projects.yaml` 时从模板复制  

若系统仍拦截：**右键 → 打开 → 打开**（首次一次即可）。无 Apple 开发者公证时，命令行无法 100% 绕过首次 Gatekeeper 弹窗。

```
dist/filekind/
├── filekind
├── 双击可整理文件.command    ← 双击运行
├── projects.yaml
├── 待整理/
└── 已整理/
```

源码仓库根目录**不包含**上述运行目录；打包脚本从 `scripts/双击可整理文件.command` 复制到 `dist/filekind/`。

## 输出目录结构

```
整理根目录/
├── 基于Android T高级智能会议平板系统/   ← 来自清单 Excel 的项目名称
│   ├── 202432--CSP311测试报告.pdf        ← 文档类直接在此目录
│   └── images/                           ← 仅图片等非文档类型有子目录
├── 基于Android R南美智能数字电视系统/
└── _未分类/
```

子目录类型可在 `projects.yaml` 的 `target_layout.subdirs_by_extension` 中配置。

## 8GB 推荐模型

| 组件 | 模型 |
|------|------|
| Embedding | `BAAI/bge-small-zh-v1.5` |
| LLM | `Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` |
| OCR | macOS：系统 Vision；其他平台：PaddleOCR（可选） |

## 工作流程

```
扫描 → 前3页提取 → 规则分类 → embedding 关联 →（可选）LLM JSON 分类 → plan.json → apply（复制）
```

工作目录 `filekind-work/<timestamp>/`：

- `plan.json`：整理计划（源路径 → 目标项目目录）
- `summary.json`：分类统计（项目数、各项目文件数）
- `files.jsonl`：分类结果（不含 raw 正文）
- `manifest.json`：执行复制后生成，用于 rollback 删除已整理副本

## 打包为可执行文件

在 macOS / Linux 上生独立运行目录 `dist/filekind/`（内含 `filekind` 可执行文件）：

```bash
chmod +x scripts/build_executable.sh
./scripts/build_executable.sh
```

或手动：

```bash
pip install -e ".[build]"
pyinstaller --noconfirm --clean filekind.spec
```

使用打包产物（目录与 `filekind` 同级）：

```
dist/filekind/
├── filekind
├── 双击可整理文件.command    ← 双击一键整理
├── _internal/
├── projects.yaml
├── 待整理/
├── 已整理/
└── filekind-work/
```

```bash
cd dist/filekind
# 文件放入 ./待整理 后，双击 双击可整理文件.command
# 或终端: ./filekind run --apply --no-dry-run
```

说明：

- 已打包：规则分类、Office/PDF 提取、**fastembed 向量**（首次运行仍会从网络拉取 bge 模型到 `~/.cache`，约 100MB）、**本地 LLM**（`build_executable.sh` 会安装 `.[llm]` 并打包 llama-cpp；GGUF 放在 `dist/filekind/models/`，见 `scripts/download_llm_model.py`）、**OCR**（macOS 优先用系统 Vision 识别扫描件；其他平台用 PaddleOCR，首次会下载模型到 `~/.paddleocr/`）
- **未打包**：无（OCR/LLM 均可在打包版中使用；重新运行 `scripts/build_executable.sh` 即可）
- 发布给客户时，可连同 `projects.example.yaml` 与 `dist/filekind/` 整个文件夹一起拷贝

## 开发

```bash
pip install -e ".[dev]"
pytest
```
