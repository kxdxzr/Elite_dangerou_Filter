"""用户提供的稀有商品来源表；只存商品、来源站和星系，不存快照价格/库存。"""

# Commodity | Station | System，保留原表名称及顺序，包括快照库存为零的来源。
_SOURCE_ROWS = """
Sothis Crystalline Gold|Newholm Station|Sothis
Soontill Relics|Cheranovsky City|Ngurii
Personal Gifts|Frost Dock|Njambalba
Jaques Quinentian Still|Jaques Station|Colonia
Kamitra Cigars|Hammel Terminal|Kamitra
Apa Vietii|Forester's Choice|Upaniklis
Mukusubii Chitin-os|Ledyard Dock|Mukusubii
Wheemete Wheat Cakes|Eisinga Enterprise|Wheemete
Kamorin Historic Weapons|Godwin Vision|Kamorin
Classified Experimental Equipment|Heart of Taurus|HIP 22460
Holva Duelling Blades|Kreutz Orbital|Holva
Volkhab Bee Drones|Vernadsky Dock|Volkhab
Karetii Couture|Sinclair Platform|Karetii
Geawen Dance Dust|Obruchev Legacy|Geawen
Kachirigin Filter Leeches|Nowak Orbital|Kachirigin
Damna Carapaces|Nemere Market|Damna
Thrutis Cream|Kingsbury Dock|Thrutis
Rapa Bao Snake Skins|Flagg Gateway|Rapa Bao
Kinago Violins|Fozard Ring|Kinago
Haiden Black Brew|Searfoss Enterprise|Haiden
Eshu Umbrellas|Shajn Terminal|Eshu
Goman Yaupon Coffee|Gustav Sporer Port|Goman
Yaso Kondi Leaf|Wheeler Market|Yaso Kondi
Onionhead Alpha Strain|Navigator Market|Xelabara
Wulpa Hyperbore Systems|Williams Gateway|Wulpa
Ochoeng Chillies|Roddenberry Gateway|Ochoeng
HIP 10175 Bush Meat|Stefanyshyn-Piper Station|HIP 10175
HIP Proto-Squid|Andersson Station|HIP 41181
Onionhead Beta Strain|la Cosa City|HIP 112974
Giant Irukama Snails|Blaauw City|Irukama
Karsuki Locusts|West Market|Karsuki Ti
Njangari Saddles|Lee Hub|Njangari
Harma Silver Sea Rum|Gabriel Enterprise|Harma
Esuseku Caviar|Savinykh Orbital|Esuseku
Vanayequi Ceratomorpha Fur|Clauss Hub|Vanayequi
Buckyball Beer Mats|Rebuy Prospect|Fullerene C60
Nguna Modern Antiques|Biggle Hub|Nguna
Toxandji Virocide|Tsunenaga Orbital|Toxandji
HIP 118311 Swarm|Lubbock Market|HIP 118311
Belalans Ray Leather|Boscovich Ring|Belalans
Alacarakmo Skin Art|Weyl Gateway|Alacarakmo
Kongga Ale|Laplace Ring|Kongga
Uzumoku Low-G Wings|Sverdrup Ring|Uzumoku
Tiegfries Synth Silk|Larbalestier Dock|Tiegfries
Hip Organophosphates|Stasheff Colony|HIP 80364
Aepyornis Egg|Glushko Station|47 Ceti
Havasupai Dream Catcher|Lovelace Port|Havasupai
Wuthielo Ku Froth|Tarter Dock|Wuthielo Ku
Sanuma Decorative Meat|Dunyach Gateway|Sanuma
Delta Phoenicis Palms|Trading Post|Delta Phoenicis
Rusani Old Smokey|Fernandes Market|Rusani
Jotun Mookah|Icelock|Jotun
Lyrae Weed|Budrys Ring|16 Lyrae
Ceremonial Heike Tea|Brunel City|Heike
Eden Apples Of Aerial|Andrade Legacy|Aerial
Rajukru Multi-Stoves|Snyder Terminal|Rajukru
Ceti Rabbits|Kaufmanis Hub|47 Ceti
Albino Quechua Mammoth Meat|Crown Ring|Quechua
Alya Body Soap|Malaspina Gateway|Alya
Momus Bog Spaniel|Tartarus Point|Momus Reach
Deuringas Truffles|Shukor Hub|Deuringas
Jaroua Rice|McCool City|Jaroua
Nanomedicines|Elion Dock|Kuma
Ultra-Compact Processor Prototypes|Langford Enterprise|17 Lyrae
Wolf Fesh|Saunders's Dive|Wolf 1301
Utgaroar Millennial Eggs|Fort Klarix|Utgaroar
Vidavantian Lace|Lee Mines|Vidavanta
Burnham Bile Distillate|Burnham Beacon|HIP 59533
Saxon Wine|Hunt Enterprise|9 Aurigae
Banki Amphibious Leather|Antonio de Andrade Vista|Banki
Lucan Onionhead|Cassie-L-Peia|Tanmark
Anduliga Fire Works|Celsius Estate|Anduliga
Eleu Thermals|Finney Dock|Eleu
Galactic Travel Guide|Bluford Orbital|LHS 3447
Borasetani Pathogenetics|Katzenstein Terminal|Borasetani
Live Hecate Sea Worms|RJH1972|Hecate
Tarach Spice|Tranquillity|Tarach Tor
HR 7221 Wheat|Veron City|HR 7221
Chameleon Cloth|Smith Reserve|LDS 883
Duradrives|Cowper Dock|Anima
Terra Mater Blood Bores|GR8Minds|Terra Mater
Witchhaul Kobe Beef|Hornby Terminal|Witchhaul
Mechucos High Tea|Brandenstein Port|Mechucos
Gilya Signature Weapons|Bell Orbital|Gilya
Ngadandari Fire Opals|Napier Terminal|Ngadandari
Any Na Coffee|Libby Orbital|Any Na
Tanmark Tranquil Tea|Cassie-L-Peia|Tanmark
Helvetitj Pearls|Friend Orbital|Helvetitj
Coquim Spongiform Victuals|Hirayama Installation|Coquim
Ethgreze Tea Buds|Bloch Station|Ethgreze
Crystalline Spheres|Snow Moon|Bento
Baltah'sine Vacuum Krill|Baltha'Sine Station|Baltah'Sine
Baked Greebles|Bamford Ring|38 Virginis
Onionhead|Harvestport|Kappa Fornacis
Giant Verrix|Greeboski's Outpost|Phiagre
Fujin Tea|Futen Spaceport|Fujin
Orrerian Vicious Brew|Sharon Lee Free Market|Orrere
Diso Ma Corn|Shifnalport|Diso
LTT Hyper Sweet|Smeaton Orbital|LTT 9360
Uszaian Tree Grub|Guest Installation|Uszaa
Gerasian Gueuze Beer|Yurchikhin Port|Geras
Bast Snake Gin|Hart Station|Bast
Leestian Evil Juice|George Lucas|Leesti
Lavian Brandy|Lave Station|Lave
Chateau De Aegaeon|Schweickart Station|Aegaeon
V Herculis Body Rub|Kaku Plant|V1090 Herculis
Tauri Chimes|Porta|39 Tauri
Arouca Conventual Sweets|Shipton Orbital|Arouca
Eranin Pearl Whisky|Azeban City|Eranin
Platinum Alloy|Artzybasheff Terminal|Nahuatl
Koro Kung Pellets|Lonchakov Orbital|Korro Kung
Non Euclidian Exotanks|Euclid Terminal|LTT 8517
Azure Milk|George Lucas|Leesti
Mokojing Beast Feast|Noli Terminal|Mokojing
Void Extract Coffee|Ehrlich Orbital|LFT 1421
Chi Eridani Marine Paste|Steve Masters|Chi Eridani
Shan's Charis Orchid|Baird Gateway|Arque
Cherbones Blood Crystals|Chalker Landing|Cherbones
Honesty Pills|King Gateway|LP 375-25
AZ Cancri Formula 42|Fisher Station|AZ Cancri
Neritus Berries|Toll Ring|Neritus
Zeessze Ant Grub Glue|Nicollier Hangar|Zeessze
Xihe Biomorphic Companions|Zhen Dock|Xihe
Motrona Experience Jelly|Pinzon Dock|Dea Motrona
Medb Starlube|Vela Dock|Medb
Altairian Skin|Solo Orbiter|Altair
Vega Slimweed|Taylor City|Vega
The Hutton Mug|Hutton Orbital|Alpha Centauri
Pantaa Prayer Sticks|Zamka Platform|George Pantazis
CD-75 Kitten Brand Coffee|Kirk Dock|CD-75 661
Tiolce Waste2Paste Units|Gordon Terminal|Tiolce
Indi Bourbon|Mansfield Orbiter|Epsilon Indi
Leathery Eggs|Ridley Scott|Zaonce
Crom Silver Fesh|Chorel Survey|Crom
Jaradharre Puzzle Box|Gohar Station|Jaradharre
Mulachi Giant Fungus|Clark Terminal|Mulachi
The Waters Of Shintara|Jameson Memorial|Shinrarta Dezhra
Master Chefs|Pataarcy Corporate|Viracocha
Aganippe Rush|Julian Market|Aganippe
Centauri Mega Gin|Hutton Orbital|Alpha Centauri
Pavonis Ear Grubs|Hooper Relay|Delta Pavonis
Ophiuch Exino Artefacts|Katzenstein Dock|36 Ophiuchi
"""

GOODS = tuple(tuple(part.strip() for part in line.split("|"))
              for line in _SOURCE_ROWS.strip().splitlines())
SOURCE_SYSTEMS = tuple(sorted({system for _, _, system in GOODS}, key=str.casefold))


def source_goods(system):
    """返回该星系的全部 (商品名, 来源站名)，匹配不区分大小写。"""
    key = str(system or "").strip().casefold()
    return tuple((commodity, station) for commodity, station, name in GOODS
                 if name.casefold() == key)


def filter_sources(query=""):
    """按星系、商品、来源站筛选；星系排序并去重。"""
    words = str(query or "").strip().casefold().split()
    matched = {system for commodity, station, system in GOODS
               if all(word in f"{commodity} {station} {system}".casefold() for word in words)}
    return tuple(system for system in SOURCE_SYSTEMS if system in matched)


def source_description(system):
    goods = source_goods(system)
    if not goods:
        return "请选择列表中的来源星系"
    return f"来源星系：{system}；" + "；".join(f"{commodity} — {station}" for commodity, station in goods)
