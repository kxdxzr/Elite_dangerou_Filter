"""Presentation-only localization. Canonical query/session values never change language."""
import re

CATALOG = {
    '复制任务来源星系': 'Copy mission source system',
    '来源停机坪（可停靠船型）': 'Source pad (ship size)',
    '来源空间站最大距离 Ls': 'Source station max arrival Ls',
    '目标星环最大距离 Ls': 'Target rings max arrival Ls',
    '匹配来源空间站': 'Matching source station', '来源站最大停机坪': 'Source station largest pad',
    '来源站距离 Ls': 'Source station arrival Ls', '目标有环天体': 'Target ringed body', '星环距离 Ls': 'Ring arrival Ls',
    '距离留空不限；来源停机坪与距离须同站满足。星环距离为最近已知有环天体的到达 Ls，不是具体 RES 位置。':
        'Blank distances mean unrestricted; pad and distance must match the same source station. Ring distance is arrival Ls to the nearest known ringed body, not a specific RES.',
    '查询目标星环距离…': 'Loading target ring arrival distances…',
    '刷新数据并查询': 'Refresh data and search', '情况未知': 'Unknown',
    '缓存信息：': 'Cache metadata: ',
    'RES（星环推定）': 'RES (inferred from rings)', '分阶段耗时：': 'Stage timings: ',
    '候选地点不保证实时任务。配对与 RES/CNB 数据来自 EDTools；非无政府小派系数量仅估计可能发任务的派系。星环视为推定 RES，不推定 Low；无地点数据标记情况未知。请在游戏中确认 BGS、声望和任务。':
        'Candidates do not guarantee live missions. EDTools supplies pairs and RES/CNB records; non-Anarchy counts estimate potential issuers. Rings imply RES, not Low; missing site data is Unknown. Verify BGS, reputation and missions in game.',
    '半径针对任务来源星系；0 不限制距离。有环推定 RES；情况未知单独标注，不作为无 RES 的证据。':
        'Radius applies to source systems; 0 removes the limit. Rings imply RES. Unknown site data is labelled separately, not evidence of no RES.',
    '获取配对与地点数据（优先有效缓存）…': 'Loading pairs and sites (valid cache preferred)…',
    '完整数据下载失败。网页最多覆盖 250 ly，保存的 HTML 只能用于对应有限半径。是否打开网页？':
        'Full dataset download failed. The website covers at most 250 ly; saved HTML only supports its finite radius. Open the website?',
    '正在查询名称候选…': 'Looking up name suggestions…',
    '输入至少两个字符联想；选择候选后使用完整名称。': 'Type at least two characters for suggestions; select a full name.',
    '已选择完整名称': 'Full name selected',
    '名称联想失败；可继续手动输入完整名称。': 'Name suggestions failed; you can still type the full name.',
    '请选择候选完整名称；不自动改写输入。': 'Select a full name from the suggestions; input is not changed automatically.',
    '未找到名称候选；不代表该派系不存在。': 'No name suggestions found; this does not mean the faction does not exist.',
    'EDTools 下载失败': 'EDTools download failed',
    'EDTools 页面下载失败。是否打开对应网页？在浏览器保存 HTML 后，点击“导入 PvE 网页”继续查询。':
        'EDTools download failed. Open the matching page? Save HTML in your browser, then use Import PvE HTML to continue.',
    'Elite 星系/空间站全条件筛选器': 'Elite Dangerous System / Station Filter',
    '类型': 'Type', '要几条': 'Results', '最多翻页': 'Max pages',
    '+ 普通条件': '+ Field condition', '+ 距离条件': '+ Distance condition',
    '清空条件': 'Clear', '保存条件': 'Save filters', '读取条件': 'Load filters',
    '运行搜索': 'Search', '停止': 'Stop', '诊断': 'Diagnostics', '导出CSV': 'Export CSV',
    '额外功能：': 'Tools:', '两系中点': 'Midpoint', '航母车位': 'Carrier parking',
    '稀有商品目标查找器': 'Rare goods target finder', '海盗任务查找器': 'Pirate massacre finder',
    '语言 / Language': '语言 / Language',
    '到星系距离': 'System distance', '最小LY': 'Min ly', '最大LY': 'Max ly',
    '范围内': 'Inside', '范围外': 'Outside', '属于其一': 'Is one of', '不属于': 'Is not one of',
    '等于': 'Equals', '不等于': 'Not equal', '包含': 'Contains', '区间(内)': 'Between',
    '是': 'True', '否': 'False', '不限': 'Any', '等级': 'Class', '级别': 'Rating',
    '新鲜度': 'Freshness', '删除': 'Delete', '选值…': 'Select…',
    '输入过滤, 勾选后确定 (多选用 ; 连接)': 'Type to filter, select values and confirm (multiple values use ;).',
    '确定': 'OK', '无需填写': 'No value needed', '快捷或手填日期': 'Preset / date',
    '填日期或近N天': 'Date / last N days', '填数字/min~max': 'Number / min~max',
    '加载中…': 'Loading…', '自由输入': 'Free text', '请填星系': 'Enter a system',
    '第三格可下拉/打字联想/点“选值…”多选 (选项≤30个直接下拉)。船/模块名打字联想+自动纠错，行内自带新鲜度选择。':
        'Choose or type values, or use Select… for multiple values. Ships/modules support suggestions, spelling correction and freshness filters.',
    '就绪': 'Ready', '名称': 'Name', '星系/位置': 'System / location',
    '关键信息': 'Details', '各参考点距离': 'Reference distances',
    '提示': 'Information', '该字段无预置选项, 直接输入即可 (星系/派系名支持模糊)。':
        'No preset values. Type a value (system/faction names support partial matching).',
    '未勾选任何值': 'No values selected', '请先添加至少一个条件': 'Add at least one condition first',
    '距离条件请填写参考星系': 'Enter a reference system for the distance condition',
    '条件有误': 'Invalid conditions', '条件自相矛盾，一次请求都没发': 'Contradictory conditions; no request sent',
    '无需检索': 'No search needed', '确认': 'Confirm',
    '没有任何条件能推给服务器，将逐页硬扫全库\n(慢，且翻页上限内未必扫全)，继续吗？':
        'No filters can be sent to the server. Scan the database page by page?\nThis is slow and the page limit may leave results incomplete.',
    '会话保存失败': 'Session save failed',
    '未关闭程序，请检查目录权限后重试。': 'The application remains open. Check directory permissions and try again.',
    '查询中...': 'Searching…', '查询中…': 'Searching…', '准备中': 'Preparing', '完成': 'Complete',
    '已停止': 'Stopped', '未完成': 'Incomplete', '失败': 'Failed', '查询失败': 'Search failed',
    '正在停止...': 'Stopping…', '停止中': 'Stopping', '诊断中': 'Diagnosing',
    '诊断中: 取前3页样本统计各条件通过率...': 'Diagnostics: measuring condition pass rates on the first 3 pages…',
    '诊断完成': 'Diagnostics complete', '诊断失败': 'Diagnostics failed',
    '通过率仅针对这些候选样本；0% 不代表全库无结果。多距离组合注意两圈是否有交集。':
        'Pass rates apply only to these samples; 0% does not mean no results exist. Check whether distance regions intersect.',
    '航母车位查找': 'Carrier parking finder', '参考星系': 'Reference system',
    '半径 ly (≤50)': 'Radius ly (≤50)', '最多页数': 'Max pages',
    '只显示站点少于20的星系': 'Only systems with fewer than 20 stations',
    '只显示确认免许可的星系': 'Only confirmed permit-free systems',
    '站点总数包含航母及地面站：<10 大概率有靠近主星的车位；10–19 大概率有车位。数据为 Spansh 已收录记录，实际车位以游戏为准。':
        'Counts include carriers and planetary stations. <10: likely parking near the main star; 10–19: likely parking. Spansh records are estimates; verify in game.',
    '输入参考星系后查询；双击结果复制星系名。': 'Enter a reference system and search. Double-click to copy a system name.',
    '星系': 'System', '距离 ly': 'Distance ly', '站点总数': 'Station count', '航母数': 'Carrier count',
    '车位判断': 'Parking estimate', '许可': 'Permit', '星系记录年龄': 'System record age',
    '查找车位': 'Find parking', '导出 CSV': 'Export CSV', '暂无结果': 'No results yet',
    '参数错误': 'Invalid parameters', '请填参考星系、半径 (大于0且不超过50 ly) 和正整数页数':
        'Enter a reference system, radius (0 < r ≤ 50 ly) and a positive integer page limit.',
    '两系中点 - 离中点最近的星系': 'Midpoint - nearest systems', 'A星系': 'System A', 'B星系': 'System B',
    '仅有人星系': 'Populated only', '排除需许可': 'Exclude permit systems', '查找': 'Find',
    '输入两星系名后点查找 (支持联想, 打错自动纠)。': 'Enter two systems and click Find (suggestions and spelling correction supported).',
    '距中点ly': 'Midpoint ly', '距A ly': 'A ly', '距B ly': 'B ly', '人口/阵营/许可': 'Population / allegiance / permit',
    '要几条请填数字': 'Enter a numeric result limit', '请填写 A、B 星系': 'Enter systems A and B',
    '查找失败': 'Search failed', '暂无结果, 先运行搜索': 'Run a search first',
    '商品来源星系': 'Goods source system', '最小距离 ly': 'Min distance ly', '最大距离 ly': 'Max distance ly',
    '每轮最多页数': 'Pages per search', '筛选来源（星系／商品／站名）': 'Filter sources (system / goods / station)',
    'Power（关联势力）': 'Power (association)', '全势力扫描（12个）': 'Scan all 12 Powers',
    '固定条件：大型停机坪、非地面站、排除航母和殖民船、Unoccupied。每个势力先查 ≤100 Ls，确认无结果后查 ≤1000 Ls。':
        'Fixed filters: large pad, non-planetary, no carriers/colonisation ships, Unoccupied. Each Power: ≤100 Ls first, then ≤1000 Ls only if no hits.',
    '每个势力最多显示5站：先按距离 ly、再按到站距离 Ls 从近到远。点击势力汇总查看该组；双击明细复制星系名。':
        'Up to 5 stations per Power, sorted by ly then arrival Ls. Select a Power for details; double-click to copy a system name.',
    '关联势力': 'Associated Power', '命中站点数': 'Matching stations', '命中星系数': 'Matching systems',
    '到站上限 Ls': 'Arrival limit Ls', '检索状态': 'Search status', '空间站': 'Station',
    '到站距离 Ls': 'Arrival Ls', '范围': 'Range', '站点记录年龄': 'Station record age',
    '标准 ≤100 Ls': 'Standard ≤100 Ls', '放宽 ≤1000 Ls': 'Extended ≤1000 Ls',
    '请先查询': 'Run a search first', '检索说明': 'Search notes',
    '请从列表选择来源星系，并填写有效距离区间和正整数页数': 'Select a source system and enter a valid distance range and positive page limit.',
    '查询失败；不能解释为无结果': 'Search failed; this does not mean no matches exist',
    '开始查询': 'Search', '全部组明细': 'All group details', '复制星系名': 'Copy system name',
    '导出全部组 CSV': 'Export all groups CSV',
    '未知': 'Unknown', '刚刚': 'Just now', '主星附近': 'Near main star', '有车位': 'Likely parking',
    '需许可': 'Permit required', '免许可': 'No permit', '未达阈值': 'Threshold not met',
    '半径 ly（0=无限）': 'Radius ly (0=unlimited)', '最少任务派系（0–8）': 'Min mission factions (0–8)',
    '最少联邦派系（0–8）': 'Min Federation factions (0–8)', '最少帝国派系（0–8）': 'Min Empire factions (0–8)',
    '来源存在派系': 'Faction present in source', '来源控制小派系': 'Source controlling minor faction',
    '目标控制小派系': 'Target controlling minor faction', '控制 Power': 'Controlling Power',
    'Power 筛选对象': 'Power filter applies to', '任务来源': 'Mission source', '击杀目标': 'Pirate target',
    '双方': 'Both', '优先 RES Low': 'Prefer RES Low', '无 RES 命中时回退 CNB': 'CNB only if no RES matches',
    '导入 PvE 网页': 'Import PvE HTML', '打开 PvE 网页': 'Open PvE website',
    '目标星系': 'Target system', '任务派系数': 'Mission factions', '联邦派系数': 'Federation factions',
    '帝国派系数': 'Empire factions', '战斗地点': 'Combat site', '来源控制派系': 'Source controller',
    '目标控制派系': 'Target controller', '来源 Power': 'Source Power', '目标 Power': 'Target Power',
    '来源更新时间': 'Source updated', '目标更新时间': 'Target updated',
    '网页文件': 'HTML file', '数据错误': 'Data error', '已导入网页；点击开始查询应用条件。': 'HTML imported; click Search to apply filters.',
    '请选择结果': 'Select a result', '复制目标星系': 'Copy target system',
    'Spansh Unoccupied；未区分 Expansion / Contested，合并关系尚未样本验证。':
        'Spansh Unoccupied; Expansion / Contested are not distinguished. Their mapping has not been verified with samples.',
    ' 使用 Power，不要求由该势力控制。': ' Uses Power association, not controlling Power.',
    '请选择列表中的来源星系': 'Choose a source system from the list',
    '来源星系：': 'Source system: ',
    '候选地点不保证实时任务。配对与 RES/CNB 数据来自 EDTools；非无政府小派系数量仅估计可能发任务的派系。请在游戏中确认 BGS 状态、声望和任务；有星环不代表有 RES。':
        'Candidates do not guarantee live missions. EDTools provides pairs and RES/CNB records; non-Anarchy faction counts only estimate potential issuers. Verify BGS, reputation and missions in game. Rings alone do not confirm RES.',
    '半径针对任务来源星系（与 EDTools 一致）；0 不限制距离。默认只查已有明确 RES/CNB 记录的配对。':
        'Radius applies to mission source systems (as on EDTools); 0 removes the distance limit. Only pairs with explicit RES/CNB records qualify.',
    '派系计数数据源': 'Faction count source', '地点原始记录': 'Original site record',
    '已完成当前数据集检索。': 'Search complete within the supplied dataset.',
    '检索未完成；不能确认不存在 RES 命中。': 'Incomplete; absence of RES matches is unconfirmed.',
    '详见检索说明。': 'See Search notes.', '数据错误 ': 'Data errors: ',
    '查询失败，不能判断有无命中。可导入浏览器保存的 EDTools PvE 网页。':
        'Search failed; no conclusion about matches. Import an EDTools PvE HTML page saved in your browser if needed.',
    '使用在线数据': 'Use online data', '已切换在线数据；点击开始查询。': 'Switched to online data; click Search.',
    '正在导入网页...': 'Importing HTML…', '导入失败；保留之前导入的数据。': 'Import failed; previous imported data retained.',
    '距离条件未填写参考星系': 'Distance condition needs a reference system',
    '模块等级必须是0~8 (如 5/5级)': 'Module class must be 0–8 (e.g. 5)',
    '模块级别必须是单个字母 (如 A/B, I表示无级别)': 'Module rating must be one letter (e.g. A/B; I means no rating)',
    '选项值为空': 'Empty option value', '检索类型必须是 stations 或 systems': 'Search type must be stations or systems',
    '请填写参考星系': 'Enter a reference system', '未知距离模式': 'Unknown distance mode',
    '缺少字段': 'Missing field', '未知比较操作': 'Unknown comparison operator', '至少选择一个值': 'Choose at least one value',
    '缺少比较值': 'Missing comparison value', '数字必须有限': 'Numbers must be finite',
    '天数必须是正整数': 'day count must be a positive integer', '必须是有限数字': 'must be a finite number',
    '最小值大于最大值': 'Minimum exceeds maximum', '无边界的范围外没有可满足的结果': 'Unbounded outside range cannot match',
    '等于条件需要数字': 'Equality requires a number', '距离圈不相交': 'Distance regions do not intersect',
    '结果数和页数必须大于零，每页数量必须在 1~500 之间': 'Result/page limits must be positive; page size must be 1–500',
    '服务器候选计数已封顶 (10000)，不代表全库总数': 'Server candidate count is capped at 10000; this is not the database total',
    '服务器重复返回同一批候选，检索未完成': 'Server repeated the same candidate batch; search incomplete',
    '部分候选缺少本地复核字段，无法确认: ': 'Some candidates lack local-check fields and cannot be verified: ',
    '达到翻页上限，检索未完成；当前命中数不是全库结果数': 'Page limit reached; search incomplete. Current hits are not the database total',
    '已手动停止，返回部分结果': 'Stopped by user; partial results returned',
    '已达到所需结果数，返回首批命中': 'Requested result count reached; first matches returned',
    '搜索半径必须大于 0 且不超过 50 ly': 'Search radius must be > 0 and ≤ 50 ly',
    '翻页上限必须是正整数': 'Page limit must be a positive integer',
    '模块名包含只本地过滤 (等级/级别已下推)': 'Module name Contains is local only (class/rating filters sent to server)',
    '多距离交集坐标包围盒已下推': 'Multi-distance intersection bounding box sent to server',
    '无(请检查拼写)': 'None (check spelling)',
    '请选择有效的 Power 势力': 'Choose a valid Power',
    '距离须满足 0 ≤ 最小距离 ≤ 最大距离，且最大距离大于0': 'Distances must satisfy 0 ≤ min ≤ max and max > 0',
    '每轮最多页数必须是正整数': 'Pages per search must be a positive integer',
    '标准范围': 'Standard range', '放宽范围': 'Extended range', '无结果': 'No results',
    '站点数据缺失，无法判断': 'Station data missing; cannot estimate parking',
    '大概率有靠近主星的车位': 'Likely parking near the main star', '大概率有车位': 'Likely parking',
    '未达到低于20的推荐阈值': 'Does not meet the recommended <20 threshold', '较拥挤': 'Crowded',
}

# Reusable fragments for live progress/result/error messages from the existing engine.
FRAGMENTS = {
    '查询目标星环距离：': 'Loading target ring arrival distances: ',
    '按控制 Power 批量预筛选：': 'Batch controlling Power prefilter: ',
    '控制 Power 分页：': 'Controlling Power pages: ', '；第 ': '; page ', ' 页；': '; ', '已读取 ': 'Read: ',
    '按控制派系批量预筛选：': 'Batch controller prefilter: ',
    '查询派系详情：': 'Loading faction details: ', '个星系，最多 ': ' systems, up to ',
    '并发…': ' concurrent requests…', '个星系': ' systems', '本地复核：': 'Local check: ',
    '条候选…': ' candidates…', '条结果；耗时 ': ' results; elapsed ', ' 秒': ' seconds',
    '明确 RES：': 'Confirmed RES: ', '星环推定：': 'Inferred from rings: ', '用时 ': 'Elapsed: ',
    '数据获取时间：': 'Data fetched at: ', '缓存命中 ': 'Cache hits: ', '显示结果：': 'Rendering results: ',
    '已纠正为 ': 'Corrected to ', '已自动纠正': 'Auto-corrected', '已保存 ': 'Saved ', '已导出 ': 'Exported ',
    '个可下拉': ' choices', '个打字筛': ' choices; type to filter', '近': 'Last ', '天': ' days',
    '分钟前': ' minutes ago', '小时前': ' hours ago', '天前': ' days ago', '多选 ': 'Select multiple ', '单选 ': 'Select one ',
    '请下拉选择或输入至少一个值, 多个用 ; 分隔': 'Select or type at least one value; separate multiple values with ;',
    '请下拉选择或输入内容': 'Select or type a value', '请填写数字': 'Enter a number',
    '区间格式为 最小~最大, 如 0~1000, 空一边表示不封口': 'Use min~max, e.g. 0~1000; leave an end blank for an open range',
    '未知操作': 'Unknown operator', '服务器候选计数 ': 'Server candidates: ', '已复核 ': 'Checked: ',
    '命中 ': 'Matches: ', '显示 ': 'Shown: ', '请求中 ': 'Requesting: ', '卖:': 'Selling: ',
    '在售': 'Selling ', '船厂': 'Shipyard', '改装': 'Outfitting', '市场': 'Market', '模块': 'modules',
    '等': ' and ', '项': ' items', '船/': 'ships / ', '条': ' rows', '最严, 优先放宽它': 'strictest; relax this first',
    '样本 ': 'Sample: ', '服务器前3页候选': 'first 3 candidate pages', '通过': 'passed',
    '检索完成': 'Search complete', '检索未完成（当前仅部分结果，不代表无命中）': 'Incomplete search (partial results, not evidence of no matches)',
    '检索未完成，当前为部分结果': 'Incomplete search; partial results', '范围内分页已取完': 'All pages in range fetched',
    '个星系；筛选后请从下拉选择': ' systems; choose from the filtered list',
    '每势力最多5条，ly优先、Ls其次': 'max 5 per Power; ly then Ls', '扫描候选 ': 'Candidates scanned: ',
    '个势力': ' Powers', '参考 ': 'Reference: ', '周围 ': ' around ', '扫描 ': 'Scanned: ',
    '站点数据未知 ': 'Unknown station data: ', '相距 ': 'separation ', '中点': 'midpoint ', '找到 ': 'Found: ',
    '势力': 'Power', '来源': 'Source', '商品': 'Goods', '到站': 'Arrival', '个': ' ',
    '已达到所需结果数': 'Requested result count reached', '候选分页已取完': 'All candidate pages fetched',
    '已手动停止': 'Stopped by user', '达到翻页上限': 'Page limit reached', '解析参考星系': 'Resolving reference system',
    '正在请求': 'Requesting', '页': 'page', '本地': 'local', '复核': 'check', '候选': 'candidates',
    '个条件服务器直查': ' server-filtered conditions', '距离范围': 'distance bounds',
    '正在解析参考星系: ': 'Resolving reference system: ', '正在请求第': 'Requesting page ',
    '服务器直查第': 'Server-filtered page ', '服务器直查': 'Server-filtered ', '每页': 'per page ',
    '已扫 ': 'Scanned: ', '已命中 ': 'Matched: ', '有效率': 'hit rate ', '尚未发送请求': 'no request sent yet',
    '服务器响应无效: ': 'Invalid server response: ', '星系不存在: ': 'System not found: ',
    '，你是不是想找: ': '; did you mean: ', '未知选项: ': 'Unknown option: ',
    '由本地过滤 (服务器不支持)': 'is filtered locally (unsupported on server)',
    '中间挖空只本地过滤': 'outside interval is local only', '新鲜度本地复核': 'freshness checked locally',
    '多行条件由本地逐行 AND 复核': 'repeated conditions checked locally with AND', '条条件需本地复核': 'conditions need local checks',
    '从交集中心检索，候选球半径 ': 'Searching from intersection centre; candidate sphere radius ',
    '矛盾: ': 'Contradiction: ', '的范围无交集': 'ranges do not intersect',
    '的距离圈不相交': 'distance regions do not intersect', '多距离交集与 ': 'Multi-distance intersection and ',
    '坐标条件不相交': 'coordinate bounds do not intersect', '已找 ': 'Found: ', '半径 ': 'Radius: ',
}


def translate(text, language='zh'):
    if not isinstance(text, str) or language != 'en':
        return text
    if text in CATALOG:
        return CATALOG[text]
    if not re.search(r'[\u3400-\u9fff]', text):
        return text
    # Field labels remain reversible through their API key in parentheses.
    field = re.fullmatch(r'.*[\u3400-\u9fff].* \(([a-z_]+)\)', text)
    if field:
        key = field.group(1)
        return f"{key.replace('_', ' ').title()} ({key})"
    text = re.sub(r'近(\d+)天', r'Last \1 days', text)
    text = re.sub(r'数据(\d+)天内', r'data within \1 days', text)
    text = re.sub(r'等(\d+)项', r' and others (\1 items)', text)
    text = re.sub(r'距(?=[^\n]*ly范围[内外])', 'Distance to ', text)
    text = re.sub(r'=否(?=由本地过滤)', '=False', text)
    catalog = dict(CATALOG, **FRAGMENTS)
    for source in sorted(catalog, key=len, reverse=True):
        # One-character operator translations must never rewrite sentences/names.
        if len(source) > 1:
            text = text.replace(source, catalog[source])
    text = re.sub(r'第(\d+)条条件', r'Condition \1', text)
    text = re.sub(r'(\d+)\s*条', r'\1 rows', text)
    text = re.sub(r'(\d+)页', r'\1', text)
    text = re.sub(r'([0-8A-I])级', r'\1', text)
    for source, target in [('；', '; '), ('，', ', '), ('：', ': '), ('。', '. '), ('、', ', ')]:
        text = text.replace(source, target)
    return text


class Localizer:
    def __init__(self, root, language='zh'):
        self.root, self.language = root, language if language in ('zh', 'en') else 'zh'
        self.callbacks = set()
        root._localizer = self

    def tr(self, text):
        return translate(text, self.language)

    def register(self, callback):
        self.callbacks.add(callback)
        callback()

    def set_language(self, language):
        if language not in ('zh', 'en'):
            raise ValueError('Unsupported language')
        self.language = language
        for callback in tuple(self.callbacks):
            callback()
