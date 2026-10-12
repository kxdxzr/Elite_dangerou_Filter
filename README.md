# Elite Dangerous 星系与空间站筛选器

基于 [Spansh](https://spansh.co.uk/) 数据的 Python 桌面工具，支持多条件筛选、买船与模块查询、航母车位估计，以及稀有商品目标查找。界面使用 tkinter，包含中文字段说明与英文游戏名称。

**项目定位：它不一定比 Inara 更好用，但提供更全面、更灵活、可自由组合的筛选条件。** 适合将重复条件、多参考点距离、模块规格和数据新鲜度等要求组合起来，作为 Inara 常用查询之外的补充工具。

仓库：[kxdxzr/Elite_dangerou_Filter](https://github.com/kxdxzr/Elite_dangerou_Filter)。

本项目由 **GPT-6.1 Sol** 通过 **vibe coding** 完成，功能根据用户需求持续迭代。

## 功能

- **通用筛选**：查询星系或空间站，可叠加重复条件；同一行多选为 OR，不同行为 AND。
- **多参考点距离**：支持多个距离范围、范围外查询，服务器预筛选后本地精确复核。
- **买船与模块查询**：模块等级／级别联动，支持同件模块规格匹配、船厂／改装数据新鲜度条件。
- **航母车位查找**：统计周围星系的站点总数（包括航母），搜索半径最大 50 ly；少于 10 标注大概率有靠近主星的车位，10–19 标注大概率有车位。
- **稀有商品目标查找器**：内置 142 个商品来源条目、138 个星系，默认 Ngurii。按来源星系、商品或来源站筛选候选，查找默认 200–220 ly 内符合 Powerplay 条件的目标站。工具内支持指定关联 Power 或扫描全 12 个势力；要求大型停机坪，排除地面站、航母及殖民船。各势力先查到站距离 ≤100 Ls，确认无命中后再放宽至 ≤1000 Ls；先按 ly、再按 Ls 排序，各组最多显示 5 站。
- **辅助操作**：进度显示、停止、条件诊断、条件保存／读取、上次会话恢复、CSV 导出，以及两系中点工具。

## GUI 截图

### 主界面：组合条件与模块规格查询

![星系与空间站筛选器主界面](docs/images/main-gui.png)

### 稀有商品目标查找器：全势力汇总与前五个目标

![稀有商品目标查找器](docs/images/rare-goods-target-finder.png)

截图展示实际查询结果，具体站点与数量会随数据更新而变化。

## 快速开始

### Windows EXE（不需要安装 Python）

[**下载 Windows 单文件 EXE**](https://github.com/kxdxzr/Elite_dangerou_Filter/releases/latest/download/EliteDangerousFilter.exe) · [所有发行版本](https://github.com/kxdxzr/Elite_dangerou_Filter/releases)

构建后的文件是 `dist/EliteDangerousFilter.exe`，双击即可启动，不需要额外的源码、缓存文件或 Python 环境。实际搜索需要联网。

EXE 已作为 [GitHub Releases](https://github.com/kxdxzr/Elite_dangerou_Filter/releases) 附件发布；源码仓库默认忽略 `dist/` 和 `build/`。

EXE 的会话和候选／规格缓存保存在 `%LOCALAPPDATA%\EliteDangerousFilter\`，不会存入单文件解包临时目录，因此关闭或移动 EXE 后仍能恢复。CSV 导出位置由用户选择。

v0.1.0 的更新版 EXE 会保存主界面条件（包括未填完整的编辑行）以及稀有商品目标查找器、航母车位、两系中点的参数。程序每 1.5 秒检查并自动保存变更，关闭主窗口或辅助窗口时也会保存；重新启动后打开对应工具即可恢复参数。写入采用原子替换；若关闭时保存失败，会提示错误并保留窗口，避免静默丢失设置。

### 从源码运行

建议使用 Python 3.10 或更高版本，且 Python 安装包含 tkinter。目前在 Windows / Python 3.13 下完成本地验证。

下载仓库或解压项目后，在项目目录运行：

```sh
python filter_gui.py
```

没有第三方 Python 依赖，不需要运行 `pip install`。可用以下命令检查 tkinter：

```sh
python -m tkinter
```

部分 Linux 发行版需要单独安装 Tk 支持。例如 Debian / Ubuntu：

```sh
sudo apt install python3-tk
python3 filter_gui.py
```

实际搜索需要网络连接，使用 Spansh API 和 EDSM 的星系坐标查询，无需配置 API key。

### 稀有商品目标查找

1. 打开 **额外功能 → 稀有商品目标查找器**。
2. 默认以 **Ngurii / Soontill Relics** 为来源，也可从内置来源列表选择其他星系。
3. 选择一个关联 **Power**，或勾选全势力扫描。
4. 点击查询；汇总显示已确认命中数量，明细只显示各势力排序后的前 5 站。
5. 点击势力查看分组明细，双击目标复制星系名，或导出 CSV。

CSV 列为：关联势力、星系、空间站、距离 ly、到站距离 Ls、范围、站点记录年龄。

## 数据口径与结果完整性

- 数据来自已收录的第三方记录，不是游戏内实时库存或实际空位查询。航母车位标注属于按站点数量做的经验估计。
- 稀有商品目标查找使用关联 `Power`，不是 `Controlled`。当前用 Spansh `Unoccupied` 作为 Inara 的 Unoccupied / Expansion / Contested 合并候选；对应关系尚未用实际星系样本验证，不能分别筛选后两种状态。
- Spansh 候选计数可能封顶于 10000，程序继续根据分页响应判断是否取完。
- 达到页数上限、停止或缺失关键字段时，会明确提示未完成／无法确认；不把未完成的零结果解释为没有目标，也不据此触发距离放宽。
- 商品来源列表保留提供时的名称，不使用原表的库存、价格、利润或距离快照；目标距离按来源坐标重新计算。

完整检索规则见 [README_检索逻辑.md](README_检索逻辑.md)。

## 命令行

`spansh_filter.py` 是单页 Spansh 查询辅助工具；GUI 的多页检索和本地复核由 `filter_engine.py` 实现。

```sh
python spansh_filter.py --help
python spansh_filter.py --kind stations --list-fields
python spansh_filter.py --kind systems --field-values power
python spansh_filter.py --kind stations --ref-system Sol --size 10 --filters-file ex_station_hitech.json
python spansh_filter.py --kind systems --ref-system Sol --size 10 --filters-file ex_system_fed.json
```

使用 JSON 文件传入过滤条件，可避免不同终端的引号转义问题。更多格式说明见 [README_筛选器说明.txt](README_筛选器说明.txt)。

## 项目结构

| 文件 | 用途 |
| --- | --- |
| `filter_gui.py` | 主 GUI、通用筛选及辅助功能 |
| `filter_engine.py` | 条件规划、分页去重、距离计算和本地复核 |
| `field_options.py` | 内置候选、模块规格和增量学习 |
| `powerplay_tool.py` | 稀有商品目标查找的势力分组、回退和排序逻辑 |
| `powerplay_gui.py` | 稀有商品目标查找窗口 |
| `rare_goods.py` | 商品来源表及候选筛选 |
| `spansh_filter.py` | CLI 及字段说明 |
| `runtime_paths.py` | 源码／EXE的持久数据目录 |
| `session_store.py` | 会话原子读写 |
| `EliteDangerousFilter.spec` | Windows 单文件 EXE 构建配置 |
| `test_*.py` | 单元与回归测试 |

### 本地数据

源码运行时，以下文件在项目目录生成或更新，已加入 `.gitignore`；EXE 运行时使用上述用户数据目录：

- `last_session.json`：上次 GUI 会话。
- `field_values_cache.json`：字段候选缓存。
- `module_specs_cache.json`：模块规格学习缓存。
- `__pycache__/`：Python 编译缓存。
- `*.csv`：导出结果。

源码中已包含船名、模块名和默认规格，首次运行不需要现成的缓存文件。

## 验证

在项目目录运行：

```sh
python -m unittest discover -v
python -m compileall -q .
```

目前包含 67 项自动化测试，覆盖条件规划、分页、距离几何、模块规格、新鲜度、航母统计、商品来源、势力分组、距离回退、排序限额、殖民船排除、运行数据路径和会话持久化。GitHub Actions 配置会在 Windows / Ubuntu 的 Python 3.10、3.13 环境运行这些检查。

GUI 交互和在线数据查询需另行实测，不包含在自动化测试中。

## 构建 Windows EXE

在 Windows 的项目目录运行（构建环境需要 Python 和 tkinter）：

```sh
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean EliteDangerousFilter.spec
```

输出 `dist/EliteDangerousFilter.exe`。构建会包含 Python、Tk 和内置数据；无需随附个人缓存或上次会话文件。

可使用 `EliteDangerousFilter.exe --smoke-test <已存在目录中的报告.json>` 验证主界面、三个辅助窗口及内置模块／商品数据加载。此模式不执行在线查询，不保存 GUI 会话；可通过环境变量 `ELITE_FILTER_DATA_DIR` 指定独立的测试数据目录。

会话跨进程验证使用独立的 `ELITE_FILTER_DATA_DIR`，先执行 `EliteDangerousFilter.exe --session-test write <报告.json>`，进程退出后再执行 `--session-test read <另一报告.json>`。它会验证自动保存、实际关闭／重新打开工具、关闭主程序、第二个进程恢复主界面草稿和三个工具的参数；不使用真实用户数据目录。

## 数据来源

- [Spansh](https://spansh.co.uk/)：星系、空间站及候选数据。
- [EDSM](https://www.edsm.net/)：参考星系坐标查询。
- [Inara](https://inara.cz/elite/)：稀有商品目标查询模板的参考。

这是社区工具，与 Frontier Developments 无隶属关系。
