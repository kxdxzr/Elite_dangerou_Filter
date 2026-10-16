# Elite_dangerous_Filter

[English](README.md) · [简体中文](README_zh-CN.md) · [Releases](https://github.com/kxdxzr/Elite_dangerous_Filter/releases)

[Detailed search logic and tool rules](docs/README_search_logic.md)

An Elite Dangerous system and station filtering desktop tool powered by [Spansh](https://spansh.co.uk/), built with Python / tkinter and an instantly switchable Chinese / English UI.

**Positioning: it may not be more convenient than Inara, but offers broader, more flexible, freely combinable filters.** It complements common lookups with more complex queries.

Repository: [kxdxzr/Elite_dangerous_Filter](https://github.com/kxdxzr/Elite_dangerous_Filter). Developed by **GPT-6.1 Sol** through **vibe coding**, with ongoing user-driven iteration.

> **v0.1.2: the colonisation candidate finder is released; the pirate massacre finder is still being tested.** Pirate results are candidate source/target pairs, not guaranteed live missions, issuer counts or RES availability. Inferred ring-based RES and explicit site records are labelled separately. Verify results in game.

## Download and run

[**Download Windows EXE**](https://github.com/kxdxzr/Elite_dangerous_Filter/releases/download/v0.1.2/EliteDangerousFilter.exe) · [v0.1.2 release notes](docs/releases/v0.1.2.md) · [All releases](https://github.com/kxdxzr/Elite_dangerous_Filter/releases)

Run `EliteDangerousFilter.exe` on 64-bit Windows; no Python installation is needed. Searches require an internet connection, but no API key.

For source execution, use **Python 3.10+ with tkinter**; there are no third-party runtime dependencies:

```sh
git clone https://github.com/kxdxzr/Elite_dangerous_Filter.git
cd Elite_dangerous_Filter
python filter_gui.py
```

Check Tk with `python -m tkinter`. Debian / Ubuntu may require `sudo apt install python3-tk` first.

Select **中文 / English** on the main window to switch all tool windows immediately. System, faction, ship and module names remain unchanged; switching language preserves raw query conditions.

## Features

- **Colonisation candidate finder (new in v0.1.2):** zero-population, station-free, permit-free systems. Independent optional regional radius and nearest-populated distance bounds, plus optional system value; editable planet and independent ring groups (all/any), moon relationships and inferred binary membership. See the [v0.1.2 release notes](docs/releases/v0.1.2.md).
- **Main-window extensions in v0.1.2:** local station/carrier/faction counts in system field rows, plus **Planet / nearest-populated conditions** for nested planet/ring groups and verified nearest-distance bounds with an editable population threshold. These combine with ordinary conditions without imposing colonisation restrictions; see [detailed rules](docs/README_search_logic.md).
- **General filters:** systems/stations, repeated conditions, OR within a multi-select row and AND between rows.
- **Distances and modules:** multiple reference points, distance intersections/outside ranges, same-item module class/rating matching, and shipyard/outfitting freshness filters.
- **Carrier parking finder:** up to 50 ly; use carrier station types catalogued by Spansh to find parking candidates, with optional inclusive minimum/maximum carrier counts. Incomplete types remain Unknown; counts are not live vacancies.
- **Rare goods target finder:** 142 source entries across 138 systems, default Ngurii and a 200–220 ly target range. Select an associated Power or scan all 12. Requires large pads; excludes planetary stations, carriers and colonisation ships. Each Power starts at ≤100 Ls and expands to ≤1000 Ls only after a complete search finds no matches. Shows up to five targets per Power, ordered by ly then Ls.
- **Pirate massacre candidates (testing):** EDTools source/target pairs and site records, with Spansh faction, issuer-count, controlling Power, source-station and target-ring filters.
- **Utilities:** system midpoint, cancellation, diagnostics, CSV export, condition files and session restoration for the main window and all five tools.

## New in v0.1.2

### Colonisation candidate finder

Open **Extra tools → Colonisation candidate finder**. This is included in the Windows EXE, not a source-only preview.

| Setting | How to use it |
| --- | --- |
| Regional reference / radius | Optionally limit candidates to a region around a reference system |
| Nearest-populated minimum / maximum ly | Independently limit distance to the nearest system with population **>1**; either bound may be blank |
| System value | Optionally require a value strictly greater than the threshold; select mapping, scan or landmark value |
| Planet groups | Add conditions for subtype, landability, terraforming, materials, signals, orbital properties and more |
| Independent ring groups | Require rings separately from the planets matched by planet groups |
| Group mode | AND requires every group to have a match; OR requires any group. Conditions within a group must match the same planet/ring |

For example, use reference **Sol**, regional radius **80 ly**, and nearest-populated bounds **4–6 ly**. Both distance filters apply together. The closest qualifying system must itself be 4–6 ly away; a more distant neighbour cannot compensate for a closer one below 4 ly. This is a usage example, not a promise of current results.

Results include the candidate, selected value, enabled distances, nearest qualifying populated system, matching planets/rings and inferred relationships. Copy-system, CSV export, cancellation, forced refresh and saved drafts are supported. Moon/binary relationships are inferred from recorded parent/orbit data, not independently confirmed in-game.

**Updated v0.1.2 EXE:** three result columns show the highest-value recorded planets by `estimated_scan_value`, descending, with planet name, type and estimated credits. Stars are excluded; mapping values and first-discovery bonuses are not substituted. Fewer than three known planets are not padded with zero values; incomplete data is labelled and rankings apply only to known values. CSV includes these columns. Existing body summaries/full records are reused without extra price-only requests.

**v0.1.2 limitation:** eligibility currently requires zero population, an explicitly permit-free record and no stations **including Fleet Carriers**. Carrier-only systems are therefore incorrectly excluded; ignoring ordinary Fleet Carriers is a pending correction, not a feature of the current EXE. These third-party checks do not guarantee a system is unclaimed or claimable. Construction-slot count filtering is not included.

### Main-window system filters

Switch the main search type to **systems**:

- Ordinary field rows now include total stations (including carriers), carrier count, total minor factions, Federation/Empire/Alliance faction counts, and non-Anarchy potential-issuer counts (total/Federation/Empire).
- Click **+ Planet / nearest-populated conditions** for planet groups, independent ring groups and nearest-populated distance bounds. Here the population threshold is editable; the default is **population >1**.
- Detailed conditions combine with ordinary rows using AND, without requiring zero population, no stations or colonisation eligibility. Saved condition files, drafts, diagnostics and complete raw-data CSV exports support these filters.

### Carrier parking finder update

The tool keeps its name. Enter optional **Min carriers / Max carriers** to filter nearby systems using inclusive bounds; blank means unrestricted and maximum **0** selects records with a confirmed zero count. Carrier types are counted from Spansh records rather than inferred from total station counts. Unknown counts do not pass an enabled count bound. These are not live parking vacancies.

See [detailed rules](docs/README_search_logic.md) and the [v0.1.2 release notes](docs/releases/v0.1.2.md). The screenshot gallery below is still from v0.1.1 and does not illustrate these additions.

**Updated v0.1.2 formatting:** ly distances across the main results and all tools use exactly two decimal places; population uses integers, and large numeric results use comma grouping (for example `1,234.50 ly`, population `1,234,567`, value `55,000 Cr`). Human-readable CSV columns and CLI text follow the same convention. Filter inputs, calculations, IDs and raw JSON remain unchanged; the main CSV's `distances_json` uses formatted strings while `raw_json` retains the original values.

Arrival distances in Ls also use exactly two decimal places throughout result tables, CSV distance columns and CLI text (for example `1,279.41 Ls`). Missing distances remain unknown, not `0.00`; this formatting does not affect Ls filter comparisons.

**Updated v0.1.2 pagination:** the colonisation finder no longer asks for a maximum page count. It automatically reads candidate pages until it reaches **Maximum results**, exhausts the supplied candidates or is stopped. Old saved page limits are ignored. With no regional bounds and restrictive conditions this can take a long time; cancellation and repeated-page/error detection remain available. Other tools' page controls are unchanged.

**Updated v0.1.2 neighbour information:** the result column is named **Nearest populated system**, with no population-count column. A separate button copies that system's name. The table/CSV show its maximum fixed-station pad (S/M/L), excluding carriers and colonisation ships; missing pad data stays Unknown. Pad information comes from the same nearest-system record, adds no request and does not select a more distant system with a larger pad. The lookup still uses population >1 and runs when a nearest-distance bound is enabled.

**Updated v0.1.2 progress:** main search and all tools show measured stage counts and percentages when a denominator is known (candidate checks, station checks, body/ring batches or requested midpoint results). Percentages describe the labelled stage, not an estimated end-to-end duration. Network preparation and capped/unknown totals remain explicitly indeterminate with known counts; page budgets are not presented as a whole-database total. Stopped, failed or incomplete searches are distinguished from completed searches.

The updated rare-goods detail table and CSV omit the redundant **Range** column. The 100 Ls / 1000 Ls fallback rule is unchanged. Re-download the asset from the existing v0.1.2 release to obtain these updates; no new version is created.

**Further local source changes (not yet in the downloadable EXE):** colonisation columns/CSV now start with candidate name → top-three scan-value planets → nearest populated system → nearest distance → maximum pad → other information. Visible copy buttons cover the main result name/system, carrier and midpoint systems, rare-goods system/station, pirate source/target/source station, and colonisation candidate/nearest system. Select a result first; absent selection or empty fields show a prompt without clearing the clipboard. Existing double-click shortcuts are retained (and added for midpoint results).

## Neutron jump planner (local source addition)

Open **Neutron jump planner** on the main window. Neutron supercharging is enabled by default. It uses Spansh's exact-plotter backend for ship-specific fuel and refuelling calculations, not the simpler fixed-range neutron router. This new sixth tool is not yet included in the downloadable v0.1.2 EXE.

- **Ship build favourites:** paste/import one Coriolis JSON or EDSY SLEF export, name it, then select, edit, rename or delete it locally. No route-favourites library or account system. Favourites use atomic writes to `route_ship_favorites.json` in the application's data directory and are excluded from Git.
- **Online calculation:** the selected build and route points are sent to Spansh. The first parse downloads a pinned EDCD/coriolis-data FSD catalogue and caches it locally. Unsupported drive/ship data is rejected rather than guessed; EDSY SLEF is preferred for unusual builds.
- **Ordered waypoints:** add, remove and move points up/down. Every leg independently assumes a **full main tank at departure**, without inherited fuel or supercharge state. The already-supercharged option applies only to leg one. Multi-leg submissions require confirmation; waypoints do **not** guarantee refuelling.
- **Results / CSV:** system, leg, ly distances, fuel, refuelling/neutron/injection flags and waypoints. Shared endpoints are merged, but prior arrival fuel and next assumed departure fuel are separate. Every leg start carries a full-tank warning. Copy selected system names or export CSV; partial exports require confirmation and retain explicit incomplete status.
- **Progress / stop:** report completed legs, not invented server calculation percentages. Cancellation stops polling and future submissions, not necessarily the server's existing job. Only validated completed legs are retained; failed/timed-out jobs are not automatically resubmitted.

See [routing details and limitations](docs/route-planner.md#english). This is an independent local UI, not browser automation or copied website graphics.

## Pirate massacre finder (testing)

Open **Extra tools → Pirate massacre finder**. All enabled filters are AND:

| Filter | Meaning |
| --- | --- |
| Reference / radius ly | Distance from **mission source to reference**, not source to target; `0` is unlimited, but the reference still controls sorting |
| Minimum total / Federation / Empire factions | Independent minima, each `0–8`; `0` disables that constraint; enabled counts estimate non-Anarchy potential issuers from Spansh |
| Faction present in source | Requires presence, not control |
| Source / target controlling minor faction | Exact full-name, case-insensitive matching; suggestions never automatically rewrite input |
| Controlling Power | Uses `controlling_power`, not associated `power`; applies to source, target or both |
| Source pad | Blank means unrestricted; S/M/L is the ship-size requirement, with larger pads accepting smaller ships |
| Source station max arrival Ls | Blank means unrestricted; **the same station with Missions service** must satisfy pad and distance. Includes planetary stations; excludes carriers, Stronghold Carriers and colonisation ships |
| Target rings max arrival Ls | Blank means unrestricted; arrival distance of the nearest known ringed body, not ring radius or a specific RES location |
| Prefer RES Low | Explicit Low sites sort first; Low is optional and is never inferred from rings |
| CNB fallback | Only after a complete search finds no matching explicit/inferred RES and no unknown-site candidates; disabled on errors or cancellation |

**Distance distinction:** radius `0` is unlimited; station/ring distances are unlimited only when blank. Entering `0` sets an actual **0 Ls** maximum. Maximum bounds are inclusive.

- Rings are labelled **RES (inferred from rings)**; missing site data is **Unknown**, not proof of no RES. When an explicit distance constraint is enabled, unknown distances do not qualify and produce unknown/incomplete diagnostics.
- Radii ≤250 ly use EDTools' explicit `/pve.php` page; `0` or >250 ly use public `pve.json` and `res.json`, with coordinate-based distances. Completeness means the supplied catalogue, not the whole galaxy. Reference, coverage, schema and row counts are validated.
- **Import PvE HTML** accepts browser-saved pages and rejects insufficient coverage. Imported site/radius-only queries can run offline when the reference name matches; other filters contact Spansh as needed.
- **Copy mission source system** and **Copy target system** copy the selected row; double-click still copies the target. Matching station and ringed-body details are included in the table and CSV.
- Controller/Power filters are batched and their detail records reused; Power uses gzip and at most four concurrent pages. Ring distances come from batched full-body records, not summaries that omit rings. Throttled progress and 200-row rendering batches preserve the full query/export results.
- EDTools cache TTL is one hour; Spansh details/controller lists/ring distances use five minutes. **Refresh data and search** switches to online data and forces refresh, without silently substituting expired data on failure. Target Power combined with source constraints may still require additional source detail lookups.

Measured locally for `Sol / unlimited / minimum 3 factions / Yuri Grom / source`: about 15.37 seconds for forced refresh and 0.19 seconds for the immediately repeated cached search, with identical results. Network conditions and changing data affect timings. Detailed rules and examples are in the [search-logic document](docs/README_search_logic.md).

## Sessions, data and limitations

- Changes auto-save every 1.5 seconds and on window close. Old sessions remain compatible; incomplete main-condition drafts, language and all five tool settings are preserved. Writes are atomic; failed close-time saves display an error and keep the window open.
- EXE data remains in `%LOCALAPPDATA%\EliteDangerousFilter\`. Source runs store sessions/build favourites in `data/` and runtime caches in `cache/`. `ELITE_FILTER_DATA_DIR` still overrides both with one isolated directory. Legacy root files migrate on access; use `python scripts/migrate_data.py` to migrate all known runtime files. Existing destination files are never overwritten; conflicts retain both copies. Personal data, caches and CSV exports are excluded from Git.
- Third-party records are not live missions, stock or vacancies. Faction counts only estimate potential issuers; verify BGS state, reputation and mission availability in game.
- Rare goods searches use associated Power. Spansh `Unoccupied` currently approximates Inara's Unoccupied / Expansion / Contested group; that mapping is unverified and the latter two cannot be filtered separately.
- Server counts may be capped. Page limits, repeated pages, missing required fields, request failures and cancellation distinguish incomplete searches from confirmed empty results.

## Development and verification

```sh
python scripts/run_tests.py
python -m compileall -q src tests scripts filter_gui.py spansh_filter.py
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean EliteDangerousFilter.spec
```

Automated tests cover the engine, sessions, localization, PvE and colonisation conditions/data integrity/cache/concurrency and real GUI interactions. Tk tests require a graphical display and are skipped on headless Linux. GitHub Actions tests Windows / Ubuntu with Python 3.10 / 3.13.

Build output: `dist/EliteDangerousFilter.exe`. Use `--smoke-test <report.json>` to verify six tool windows and both languages. Run `--session-test write <report.json>` and `--session-test read <another-report.json>` in separate processes to verify restoration. Session tests require an isolated `ELITE_FILTER_DATA_DIR`; report directories must already exist.

CLI entry point: `python spansh_filter.py --help`. Root launchers retain the old commands; implementation modules live in `src/`. Tests are in `tests/`, runnable helpers in `scripts/`, sample filters in `examples/`, and detailed documentation/screenshots in `docs/`. Example: `python spansh_filter.py --kind stations --ref-system Sol --filters-file examples/ex_station_hitech.json`. Root-level `python -m unittest discover -v` also remains supported. Runtime EXE self-check modules stay in `src/` because the application loads them with `--smoke-test` / `--session-test`.

## Screenshots

These English-interface screenshots show the v0.1.1 main window and four original tools, captured on 2026-10-14. They do not yet show the new colonisation tool or updated carrier filters in v0.1.2; results change with upstream data. For Chinese-interface screenshots, see the [Chinese README](README_zh-CN.md#截图).

### Main window

![Main GUI in English](docs/images/main-gui-en.png)

### Rare goods target finder

![Rare goods target finder in English](docs/images/rare-goods-target-finder-en.png)

### Pirate massacre finder (testing)

Two views of the same query: the result overview, followed by the table scrolled right to show the matching source station and target ring distances.

**Result overview**

![Pirate massacre finder filters and results in English](docs/images/pirate-massacre-finder-summary-en.png)

**Station and ring distance details**

![Pirate massacre finder station and ring distance details in English](docs/images/pirate-massacre-finder-en.png)

### Carrier parking finder

Historical v0.1.1 screenshot: Sol within 15 ly, with station/carrier counts and the old parking estimates. v0.1.2 replaces those estimates with carrier-count bounds, retaining the tool name. Neither version reports live vacancies.

![Carrier parking finder in English](docs/images/carrier-parking-finder-en.png)

### System midpoint finder

Nearest recorded systems to the Sol–Ngurii midpoint, with distance to the midpoint and both endpoints.

![System midpoint finder in English](docs/images/system-midpoint-finder-en.png)

## Data sources

- [Spansh](https://spansh.co.uk/): systems, stations, factions and full body data.
- [EDSM](https://www.edsm.net/): reference-system coordinates.
- [EDTools / CMDR VicTic](https://edtools.cc/pve.php): source/target pairs and explicit RES/CNB records, not a live mission API.
- [Inara](https://inara.cz/elite/): reference for the rare-goods target template.

Community project, not affiliated with Frontier Developments.
