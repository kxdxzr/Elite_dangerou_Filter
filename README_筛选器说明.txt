Elite Dangerous 星系与空间站筛选器 - CLI 说明
数据源：Spansh。当前接口无需 API key，实际查询需要网络连接。
GUI 使用方法见 README.md，检索规则见 README_检索逻辑.md。

================ 快速开始 ================
在项目目录运行：
python filter_gui.py
python spansh_filter.py --help
python spansh_filter.py --kind stations --list-fields
python spansh_filter.py --kind systems --list-fields

# 查字段允许值 (拼写必须对, 不确定就先查)
python spansh_filter.py --kind stations --field-values services
python spansh_filter.py --kind stations --field-values type
python spansh_filter.py --kind stations --field-values ships
python spansh_filter.py --kind systems --field-values power

================ 常用例子 ================
# 1. Sol附近 High Tech + 有市场 + 大垫 + 到站距离不超过5000 Ls
python spansh_filter.py --kind stations --ref-system Sol --size 10 --filters-file ex_station_hitech.json

# 2. 联邦 + High Tech + 人口不少于1M + Sol附近500 ly内
python spansh_filter.py --kind systems --ref-system Sol --size 10 --filters-file ex_system_fed.json

# 3. 原始结果输出JSON，可自行指定导出文件名
python spansh_filter.py --kind stations --ref-system Sol --size 50 --output json --filters-file ex_station_hitech.json

CLI 仅请求一页；--page 从0开始。多页遍历、本地复核与条件矛盾检查请使用GUI或filter_engine.search。
推荐用 --filters-file，避免 PowerShell、cmd 与其他终端的 JSON 引号转义差异。

================ filters 写法 ================
- 枚举多选: {"primary_economy":{"value":["High Tech"]}}
- 布尔真值: {"has_market":{"value":true}}；false 不能按此格式直接下推，应由GUI本地复核。
- 数值范围: {"distance_to_arrival":{"comparison":"<=>","value":[0,1000]}}
  数值过滤必须给出两个有限端点；单边范围可用领域上下界（人口上界示例为1000000000000000）。
- 集合名称: {"ships":[{"name":{"value":["Anaconda"]}}]}
  services/modules 使用相同的条目格式；marketplace 的子字段名为 commodity。
- 距离是特殊格式: {"distance":{"min":200,"max":220}}，与普通数值字段不同。
- 原始API字段名和GUI别名可能不同。例如更新时间原名为 market_updated_at，控制派系为 controlling_minor_faction。
  时间条件建议在GUI中配置，以统一处理时区和相对日期。
- 参考点二选一: --ref-system Sol  或  --ref-coords x,y,z
  有参考点才能用 distance 排序/过滤, 否则去掉默认sort或改成 [{"updated_at":{"direction":"desc"}}]

================ 空间站字段概览 (stations) ================
allegiance / government / state / primary_economy / secondary_economy / type /
has_market / has_shipyard / has_outfitting / has_large_pad / is_planetary /
large_pads / medium_pads / small_pads / distance_to_arrival / distance /
services / material_trader(Manufactured/Raw/Encoded) / technology_broker(Human/Guardian/Sirius) /
ships / modules / marketplace / export_commodities / import_commodities / prohibited_commodities /
controlling_faction / controlling_faction_state / controlling_faction_influence /
system_name / system_population / system_power / system_power_state / system_controlling_power /
system_primary_economy / system_secondary_economy / system_colonised / system_being_colonised /
body_name / body_type / body_subtype / body_has_atmosphere / body_has_rings / body_gravity /
carrier_name / carrier_docking_access / dssa_carrier / name /
last_updated_at / market_last_updated_at / shipyard_last_updated_at / outfitting_last_updated_at
详情及完整GUI词条用 --list-fields 看；CLI原始JSON需要API字段名，并不会自动转换GUI别名。

================ 星系字段概览 (systems) ================
name / allegiance / government / state / primary_economy / secondary_economy /
security(High/Medium/Low/Anarchy) / population / needs_permit / known_permit /
is_colonised / being_colonised / body_count / bodies / stations /
distance / distance_to_nearest_populated_system /
controlling_faction / controlling_faction_state / faction_presence /
power / controlling_power / power_state / power_state_control_progress / power_state_reinforcement / power_state_undermining /
region / landmarks / landmark_value / estimated_scan_value / estimated_mapping_value /
thargoid_war_state / thargoid_war_progress / synthesis_recipes / last_updated_at

================ 和 Inara 筛选的对应关系 ================
常用字段参考对应关系：
登陆垫 Small/Medium/Large -> has_large_pad + large/medium/small_pads
station distance Ls -> distance_to_arrival
surface / fleet carrier -> is_planetary / type=Drake-Class Carrier + carrier_docking_access
services 全列表 -> services (值名几乎一致, 可用 --field-values services 核对)
economy / allegiance / government -> 对应经济、阵营、政府字段
Power -> power (星系) / system_power (空间站所属星系)
Power controlled -> controlling_power / system_controlling_power，与关联Power不同
Powerplay状态 -> power_state / system_power_state；Spansh目前只有四种状态，不能确认与Inara六种状态完全等价
价格时效/供需量 -> market_updated_at + market条目；记录不等同于实时价格

其他字段：天体重力/大气/环、派系影响力、殖民状态、Thargoid战争、预估扫描/测绘价值、DSSA等。
可用字段与返回数据可能不同，实际支持情况以API响应和GUI诊断为准。
