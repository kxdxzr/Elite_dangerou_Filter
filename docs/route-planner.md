# Neutron jump planner / 中子星跳跃规划器

## English

This is a local-source addition, not yet part of the downloadable v0.1.2 EXE.

Neutron supercharging is enabled by default. The backend remains Spansh's exact-plotter `/api/generic/route` for ship-specific fuel and refuelling planning, not the fixed-range neutron router. An ordinary jump may still be part of a neutron-assisted route.

### Builds and local storage

- Import exactly one Coriolis JSON build or EDSY SLEF (an object or a single-element SLEF array), not a website URL. Only named ship builds are persisted; there is no route-favourites library. Corrupt favourites are reported, never silently replaced with an empty library. No personal Journal directory or commander profile is read automatically.
- The selected JSON and route points are submitted to Spansh when planning. Do not include private data you do not wish to send. First parsing downloads FSD facts from a pinned [EDCD/coriolis-data revision](https://github.com/EDCD/coriolis-data/tree/0db9234b5b9ce8c939ea84133d7ce336eea88e27); see its [licence](https://github.com/EDCD/coriolis-data/blob/0db9234b5b9ce8c939ea84133d7ce336eea88e27/LICENSE.md). Its JSON data is copyrighted by Frontier and subject to Frontier's terms; the repository's MIT licence applies to Coriolis code, not the JSON data. This application does not bundle that catalogue; successful downloads cache locally as `route_module_cache.json`.
- SLEF uses final engineered optimal mass and max fuel per jump without rounding. Coriolis applies optimal-mass modifications and supported experimental effects. Unknown FSDs, reservoirs, experimental effects or unsupported max-fuel modifications require SLEF instead of guessed physical parameters. The protocol follows the observed Spansh form request, not a guarantee of future API compatibility.

### Multi-leg semantics

- Route points are resolved by exact case-insensitive name. Validate all points before submitting jobs. Adjacent duplicates are rejected; non-adjacent revisits are allowed. Each leg submits `/api/generic/route` and polls `/api/results/{job}` sequentially with backoff. HTTP reads and timeouts are bounded, server calculation budget is 60 seconds per leg and local polling deadline is ten minutes per leg. Unknown states, invalid jobs, malformed jumps or wrong endpoints fail rather than silently skipping a leg. There is no automatic resubmission.
- Each leg uses the original full main-tank capacity, never a smaller tank to simulate remaining fuel. Shared endpoints are merged, retaining previous-leg arrival fuel separately from next-leg assumed departure fuel. Already-supercharged is only an initial flag for leg one; subsequent legs start without that assumption. This is **not a continuous-fuel route**. The tool does not verify refuelling facilities or scoopable stars at waypoints.
- CSV includes leg/departure/waypoint/full-tank markers and incomplete-route status; textual formula cells are escaped. Cancellation or failure preserves only validated complete legs, and partial export requires confirmation. Distances use two decimals and comma grouping without changing raw values. The displayed remaining distance is to the **current leg's destination**, not the final trip destination.
- At shared endpoints, leg/fuel-used/arrival fields describe arrival on the preceding leg, while the explicit departure-leg/full-tank columns and refuel/neutron/injection flags describe departure on the next leg. Next-leg departure actions are not discarded during endpoint merging.
- Stop cancels local polling and future submissions; it does not guarantee cancellation of an already-submitted server job. The current HTTP call may finish or time out before cancellation is observed. Progress measures completed legs, not server calculation time.

### Validation

Tests cover parsing/engineering, favourite persistence/corruption, full-tank boundaries, endpoint checks, partial results, cancellation, CSV and bilingual GUI actions. An online two-leg smoke query `Sol → Alpha Centauri → Barnard's Star` succeeded with a synthetic validation build. At Alpha Centauri, arrival fuel was about 31.98718 t and the next leg correctly restarted from the assumed 32 t; this is not a refuelling-availability check or an endorsement of that build.

## 中文

本功能目前仅在本地源码中，尚未包含在可下载的 v0.1.2 EXE。

默认启用中子增压，后端仍使用 Spansh exact-plotter 的 `/api/generic/route` 按配船规划燃油与补油，不是固定跳距的中子路线接口；中子辅助路线仍可能包含普通跳跃。

### 配船与本地保存

- 导入单个 Coriolis JSON 或 EDSY SLEF（对象或单元素 SLEF 数组），不接受网页链接。仅保存命名舰船配置，不做航线收藏库。收藏文件损坏时提示，不静默重置为空；不自动读取个人 Journal 目录或指挥官档案。
- 规划时向 Spansh 发送所选 JSON 和航点，请勿包含不愿发送的私人信息。首次解析下载 [EDCD/coriolis-data 固定版本](https://github.com/EDCD/coriolis-data/tree/0db9234b5b9ce8c939ea84133d7ce336eea88e27)，[许可原文](https://github.com/EDCD/coriolis-data/blob/0db9234b5b9ce8c939ea84133d7ce336eea88e27/LICENSE.md)区分：JSON 数据版权属于 Frontier，受其条款约束；MIT 仅适用于 Coriolis 代码，不适用于 JSON 数据。程序不捆绑分发该目录，下载成功后本地缓存为 `route_module_cache.json`。
- SLEF 使用工程后的最优质量／单跳最大燃油，不舍入。Coriolis 应用最优质量修正及支持的实验效果。未知 FSD、备用油箱、实验效果或不支持的单跳燃油修改明确要求改用 SLEF，不猜测物理参数。按目前观察到的 Spansh 表单协议提交，网站未来变化可能需要更新客户端。

### 多段规则

- 星系全名大小写不敏感匹配，全部航点解析成功后才提交。拒绝相邻重复点，允许非相邻重访。各段依次提交 `/api/generic/route` 并退避轮询 `/api/results/{job}`；HTTP 读取／超时受限，服务器每段计算预算60秒、本地轮询上限10分钟。未知状态、无效任务、无效跳跃或端点不匹配即失败，不跳过、不自动重提。
- 每段以原主油箱容量满油出发，不缩小油箱模拟剩余油量。合并共享端点时，分别保留前段到达燃油和后段假定出发燃油。“第一段已增压”仅用于首段，后续分段不沿用已增压假设。此为独立满油分段，**不保证燃油连续**，也不验证途经点有无补油设施／可吸油恒星。
- CSV 保留分段、出发段、途经点、满油提醒及未完成状态，转义可能触发公式的文本。取消或失败仅保留已验证的完整前段；部分导出需确认。距离两位小数、千位逗号，不修改原始值。剩余距离指**当前分段终点**，不是全程终点。
- 共享端点的分段／到达油量／本跳耗油描述前段到达；出发段／满油提醒及补油／中子／注入标记描述后段出发，合并时不会丢弃后段起点的出发操作。
- 停止取消本地轮询和后续提交，不保证撤销服务器已有任务；当前 HTTP 调用返回／超时后才可能响应取消。进度按完成分段计数，不是服务器计算耗时百分比。

### 验证

测试覆盖配船／工程、收藏保存及损坏、满油交界、端点核查、部分结果、停止、CSV 和双语 GUI。使用合成验证配船的在线两段查询 `Sol → Alpha Centauri → Barnard's Star` 已成功；Alpha Centauri 到达油量约31.98718 t，下一段确实重新按32 t出发。此测试不验证能否补油，也不构成推荐配船。
