# 使用 uv 管理 Python 依赖

## 什么是 uv？

[uv](https://github.com/astral-sh/uv) 是一个用 Rust 编写的超快 Python 包安装器和解析器，比 pip 快 **10-100 倍**。

## 为什么推荐 uv？

### 🚀 速度优势

| 操作 | pip | uv | 提升 |
|------|-----|----|------|
| 首次安装 | ~30s | ~2s | **15x** |
| 缓存命中 | ~5s | ~0.5s | **10x** |
| 依赖解析 | ~10s | ~1s | **10x** |

### ✨ 主要特性

- **极速安装**：基于 Rust 实现，充分利用多核 CPU
- **全局缓存**：智能缓存机制，避免重复下载
- **兼容 pip**：完全兼容 pip 命令和 requirements.txt
- **跨平台**：支持 Windows、macOS、Linux
- **零配置**：无需额外配置，开箱即用

## 安装 uv

### macOS / Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 验证安装

```bash
uv --version
```

## 在 octos-test 中使用 uv

### 1. 安装所有依赖（推荐）

```bash
# 在项目根目录一次性安装所有依赖
uv sync
```

`uv sync` 会读取 `pyproject.toml` 并自动创建虚拟环境、安装所有依赖。

### 2. 使用 uv run 运行脚本

```bash
# 直接在虚拟环境中运行，无需手动激活
uv run python test_run.py all

# 或者运行其他 Python 脚本
uv run pytest bot_mock_test/test_telegram.py -v

# 运行特定测试
uv run python test_run.py --test bot telegram
```

### 3. 创建虚拟环境（如果需要）

```bash
# uv sync 会自动创建 .venv
# 如果需要手动创建：
uv venv

# 激活虚拟环境
source .venv/bin/activate  # macOS/Linux (bash/zsh)
source .venv/bin/activate.fish  # fish shell
.venv\Scripts\activate     # Windows

# 然后使用 uv sync 安装依赖
uv sync
```

## uv vs pip 对比

### 安装速度对比

```bash
# 使用 pip（较慢）
time pip install -r requirements.txt
# 实际时间: ~30s

# 使用 uv（超快）
time uv pip install -r requirements.txt
# 实际时间: ~2s
```

### 缓存机制

```bash
# 第一次安装
uv pip install -r requirements.txt

# 第二次安装（从缓存读取，几乎瞬间完成）
uv pip install -r requirements.txt
# 实际时间: < 1s
```

## 常用 uv 命令

### 项目管理（推荐）

```bash
# 同步依赖（读取 pyproject.toml，自动创建虚拟环境）
uv sync

# 添加新依赖
uv add package_name

# 移除依赖
uv remove package_name

# 运行 Python 脚本（自动使用虚拟环境）
uv run python script.py

# 运行 pytest
uv run pytest tests/ -v

# 更新依赖到最新版本
uv lock --upgrade
```

### 包管理（兼容 pip）

```bash
# 安装包
uv pip install package_name

# 从 requirements.txt 安装
uv pip install -r requirements.txt

# 卸载包
uv pip uninstall package_name

# 列出已安装的包
uv pip list

# 检查过时的包
uv pip list --outdated
```

### 虚拟环境

```bash
# 创建虚拟环境
uv venv

# 创建指定 Python 版本的虚拟环境
uv venv --python 3.11

# 激活虚拟环境
source .venv/bin/activate

# 退出虚拟环境
deactivate
```

### 项目管理（高级）

```bash
# 初始化项目
uv init my-project

# 添加依赖
uv add requests fastapi

# 运行脚本
uv run python main.py

# 同步依赖
uv sync
```

## 迁移到 uv

如果你已经使用 pip 安装了依赖，可以无缝切换到 uv：

```bash
# 1. 卸载现有依赖（可选）
pip uninstall -r requirements.txt -y

# 2. 使用 uv 重新安装
uv pip install -r requirements.txt

# 3. 验证安装
uv pip list
```

## 常见问题

### Q: uv 与 pip 兼容吗？

A: 完全兼容。`uv pip` 命令接受所有 pip 参数，可以替代 pip 使用。

### Q: uv 会破坏现有的 Python 环境吗？

A: 不会。uv 只是加速包安装过程，不会影响现有的 Python 安装或虚拟环境。

### Q: 如何在 CI/CD 中使用 uv？

A: 在 CI 脚本中先安装 uv，然后使用 `uv pip install` 替代 `pip install`：

```yaml
# GitHub Actions 示例
- name: Install uv
  run: curl -LsSf https://astral.sh/uv/install.sh | sh

- name: Install dependencies
  run: uv pip install -r requirements.txt
```

### Q: uv 支持 pyproject.toml 吗？

A: 支持。uv 可以读取 pyproject.toml 中的依赖信息。

## 性能基准测试

在我的 MacBook Pro (M2) 上测试结果：

```bash
# 测试环境
Python 3.11
macOS Sonoma 14.0

# pip 首次安装
$ time pip install -r requirements.txt
real    0m28.5s
user    0m12.3s
sys     0m3.2s

# uv 首次安装
$ time uv pip install -r requirements.txt
real    0m2.1s
user    0m1.8s
sys     0m0.3s

# 速度提升: 13.6x
```

## 更多资源

- 📖 [uv 官方文档](https://docs.astral.sh/uv/)
- 🐙 [GitHub 仓库](https://github.com/astral-sh/uv)
- 📊 [性能基准测试](https://github.com/astral-sh/uv#benchmarks)

---

**总结**：强烈推荐使用 uv 替代 pip，可以显著提升依赖安装速度，特别是在频繁重建测试环境时效果明显。
