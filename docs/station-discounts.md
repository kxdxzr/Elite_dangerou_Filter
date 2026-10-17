# Public station / Power discounts · 地点／势力公共优惠

Rules checked against the community-maintained [Discounts list](https://elite-dangerous.fandom.com/wiki/Discounts) and [Li Yong-Rui](https://elite-dangerous.fandom.com/wiki/Li_Yong-Rui) page on 2026-10-17. These are rule-based candidates, not live checkout-price validation. No standard-price catalogue is fetched. Associated Power alone is insufficient: Power rules require `system_controlling_power` and a supported `system_power_state`. Carrier listings do not inherit retail discounts.

规则核对日期为2026-10-17；来源为上述社区维护资料，不代表实时结算验证。不下载价格表，势力规则要求实际控制势力与对应状态，不将关联 Power 当作控制关系，航母列表不继承零售站优惠。

| Source / 来源 | Scope / 适用范围 | Reduction / 优惠幅度 |
| --- | --- | --- |
| Li Yong-Rui, Fortified / Stronghold | Ships and modules / 舰船及模组 | 15% |
| Jameson Memorial, Shinrarta Dezhra | Ships and modules / 舰船及模组 | 10% |
| Denton Patreus, Exploited / Fortified / Stronghold | Imperial Eagle, Courier, Clipper, Cutter | 10% |
| Edmund Mahon, Exploited / Fortified / Stronghold | Cargo Rack, Hull Reinforcement Package | 20% |
| Jerome Archer, Exploited / Fortified; Stronghold | Combat weapon hardpoints, excluding mining / 战斗武器挂点，不含采矿 | 10%; 20% |
| Alioth | Known Lakon ships / 已知 Lakon 舰船 | 5% |
| Irkutsk, Alioth | Asp Explorer, Orca | 20% |
| Hamilton Gateway, Wolf 406 | Diamondback Explorer, if stocked / 有货时 | 20% |
| Henry O'Hare's Hangar, Summerland | Imperial Eagle, Courier, Clipper, Cutter | 10% |
| Daedalus, Sol | Federal Dropship, Vulture; Eagle | 10%; 20% |
| Edmondson High, Beta Hydri | Eagle | 10% |
| Attilius Orbital, CD-43 11917 | Selected ships; selected small/medium non-turret weapons and chaff/heat sinks / 指定舰船；指定小中型非炮塔武器及箔条／散热器 | 20%; 30% |

Each requested item must still exist in the returned stock and match its name and module class/rating. Location rules require both system and station identity. Missing details or unmatched rules do not qualify for **True**. This is not an exhaustive discount catalogue: personal Elite/pledge bonuses, expired CG sales and unconfirmed new products are excluded. Overlapping rules show the strongest single known reduction, not an invented stacked percentage. Legacy unfinished **False** selections become **Any**.

仍须在实际返回库存中找到同件商品，并满足名称及模组等级／级别；地点优惠同时匹配星系与站名。证据缺失或没有已知规则不命中“是”。规则并非穷尽所有优惠：不计算个人 Elite／效忠奖励、过期社区目标优惠或未经确认的新商品。同件商品有多条规则时显示最大单项优惠，不猜叠加比例。旧版未完成的“否”选择转换为“不限”。

UI/CSV show **matched item**, **class**, **rating**, **discount %**, and **source** in separate columns as applicable. Percentages mean price reductions: **15 = 15% off = 85% of original price**, not a 15%-of-original purchase price. Verify access permits, stock and final prices in game.

界面及CSV按需分列显示命中商品、等级、级别、优惠幅度及来源；**15表示减价15%，即85折**，不是原价的15%。请在游戏内复核许可、库存及最终结算价。
