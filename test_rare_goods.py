import unittest

import rare_goods as sources


class RareGoodsTests(unittest.TestCase):
    def test_user_table_coverage_and_default(self):
        self.assertEqual(len(sources.GOODS), 142)
        self.assertEqual(len(sources.SOURCE_SYSTEMS), 138)
        self.assertEqual(len({row[0] for row in sources.GOODS}), 142)
        self.assertTrue(all(len(row) == 3 and all(row) for row in sources.GOODS))
        self.assertEqual(sources.source_goods("Ngurii"), (("Soontill Relics", "Cheranovsky City"),))
        # 库存为零、远距离及表格末尾的来源不丢弃。
        self.assertTrue({"HIP 22460", "Kamorin", "Colonia", "36 Ophiuchi", "Delta Pavonis"}
                        <= set(sources.SOURCE_SYSTEMS))

    def test_shared_systems_keep_all_goods_and_stations(self):
        expected = {
            "47 Ceti": (("Aepyornis Egg", "Glushko Station"), ("Ceti Rabbits", "Kaufmanis Hub")),
            "Alpha Centauri": (("The Hutton Mug", "Hutton Orbital"), ("Centauri Mega Gin", "Hutton Orbital")),
            "Leesti": (("Leestian Evil Juice", "George Lucas"), ("Azure Milk", "George Lucas")),
            "Tanmark": (("Lucan Onionhead", "Cassie-L-Peia"), ("Tanmark Tranquil Tea", "Cassie-L-Peia")),
        }
        for system, goods in expected.items():
            with self.subTest(system=system):
                self.assertEqual(sources.SOURCE_SYSTEMS.count(system), 1)
                self.assertEqual(sources.source_goods(system), goods)

    def test_keyword_search_by_system_commodity_and_station(self):
        self.assertEqual(sources.filter_sources(""), sources.SOURCE_SYSTEMS)
        self.assertEqual(sources.filter_sources("  soontill RELICS  "), ("Ngurii",))
        self.assertEqual(sources.filter_sources("Cheranovsky"), ("Ngurii",))
        self.assertEqual(sources.filter_sources("Hutton"), ("Alpha Centauri",))
        self.assertEqual(sources.filter_sources("47 rabbits"), ("47 Ceti",))
        self.assertEqual(sources.filter_sources("C60"), ("Fullerene C60",))
        self.assertEqual(sources.filter_sources("No Such Rare Commodity"), ())

    def test_description_and_punctuation(self):
        self.assertEqual(sources.source_goods("  ngurii "), sources.source_goods("Ngurii"))
        description = sources.source_description("47 Ceti")
        for name in ("Aepyornis Egg", "Glushko Station", "Ceti Rabbits", "Kaufmanis Hub"):
            self.assertIn(name, description)
        self.assertEqual(sources.filter_sources("Saunders's Dive"), ("Wolf 1301",))
        self.assertEqual(sources.filter_sources("Baltah'Sine"), ("Baltah'Sine",))
        self.assertFalse(sources.source_goods("Sol"))


if __name__ == "__main__":
    unittest.main()
