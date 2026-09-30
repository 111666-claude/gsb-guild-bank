import random
import unittest

from guildbank.core import MS_PER_DAY, GuildBank


class DepositTest(unittest.TestCase):
    def test_deposit_increases_stock(self):
        bank = GuildBank()
        bank.deposit("op-1", "p", "ore", 5, 0)
        self.assertEqual(bank.stock["ore"], 5)

    def test_deposit_writes_log(self):
        bank = GuildBank()
        bank.deposit("op-1", "p", "ore", 5, 0)
        self.assertEqual(len(bank.log), 1)


class AuditTest(unittest.TestCase):
    def test_audit_of_empty_bank(self):
        self.assertEqual(GuildBank().audit("ore", 0), 0)

    def test_audit_counts_deposit(self):
        bank = GuildBank()
        bank.deposit("op-1", "p", "ore", 7, 0)
        self.assertEqual(bank.audit("ore", 0), 7)


class WithdrawTest(unittest.TestCase):
    def test_withdraw_returns_count(self):
        bank = GuildBank(quota_per_day=100)
        bank.deposit("op-1", "p", "ore", 10, 0)
        self.assertEqual(bank.withdraw("op-2", "p", "ore", 4, 100), 4)


class IdempotencyTest(unittest.TestCase):
    def test_duplicate_deposit_returns_false_and_changes_nothing(self):
        bank = GuildBank()
        self.assertTrue(bank.deposit("op-1", "p", "ore", 5, 0))
        self.assertFalse(bank.deposit("op-1", "p", "ore", 5, 10))
        self.assertEqual(bank.stock["ore"], 5)
        self.assertEqual(len(bank.log), 1)
        self.assertEqual(bank.audit("ore", 20), 5)

    def test_duplicate_withdraw_returns_zero_and_changes_nothing(self):
        bank = GuildBank(quota_per_day=100)
        bank.deposit("op-1", "p", "ore", 10, 0)
        self.assertEqual(bank.withdraw("op-2", "p", "ore", 4, 100), 4)
        self.assertEqual(bank.withdraw("op-2", "p", "ore", 4, 200), 0)
        self.assertEqual(bank.stock["ore"], 6)
        self.assertEqual(len(bank.log), 2)
        self.assertEqual(bank.daily[("p", 0)], 4)

    def test_op_id_shared_across_deposit_and_withdraw(self):
        bank = GuildBank(quota_per_day=100)
        bank.deposit("op-1", "p", "ore", 10, 0)
        self.assertEqual(bank.withdraw("op-1", "p", "ore", 3, 100), 0)
        self.assertEqual(bank.stock["ore"], 10)


class QuotaTest(unittest.TestCase):
    def test_over_quota_rejected_without_touching_stock(self):
        bank = GuildBank(quota_per_day=10)
        bank.deposit("op-1", "p", "ore", 50, 0)
        self.assertEqual(bank.withdraw("op-2", "p", "ore", 15, 100), 0)
        self.assertEqual(bank.stock["ore"], 50)
        self.assertEqual(bank.audit("ore", 200), 50)

    def test_quota_accumulates_within_one_day(self):
        bank = GuildBank(quota_per_day=10)
        bank.deposit("op-1", "p", "ore", 50, 0)
        self.assertEqual(bank.withdraw("op-2", "p", "ore", 6, 100), 6)
        self.assertEqual(bank.withdraw("op-3", "p", "ore", 5, 200), 0)
        self.assertEqual(bank.withdraw("op-4", "p", "ore", 4, 300), 4)

    def test_quota_resets_next_service_day(self):
        bank = GuildBank(quota_per_day=10)
        bank.deposit("op-1", "p", "ore", 50, 0)
        self.assertEqual(bank.withdraw("op-2", "p", "ore", 10, 0), 10)
        self.assertEqual(bank.withdraw("op-3", "p", "ore", 1, 100), 0)
        self.assertEqual(bank.withdraw("op-4", "p", "ore", 10, MS_PER_DAY), 10)

    def test_quota_is_per_player(self):
        bank = GuildBank(quota_per_day=10)
        bank.deposit("op-1", "p", "ore", 50, 0)
        self.assertEqual(bank.withdraw("op-2", "pa", "ore", 10, 0), 10)
        self.assertEqual(bank.withdraw("op-3", "pb", "ore", 10, 0), 10)


class ConservationTest(unittest.TestCase):
    def test_withdraw_deducts_stock(self):
        bank = GuildBank(quota_per_day=100)
        bank.deposit("op-1", "p", "ore", 10, 0)
        bank.withdraw("op-2", "p", "ore", 4, 100)
        self.assertEqual(bank.stock["ore"], 6)

    def test_insufficient_stock_rejected(self):
        bank = GuildBank(quota_per_day=100)
        bank.deposit("op-1", "p", "ore", 10, 0)
        bank.withdraw("op-2", "p", "ore", 4, 100)
        self.assertEqual(bank.withdraw("op-3", "p", "ore", 20, 200), 0)
        self.assertEqual(bank.stock["ore"], 6)
        self.assertEqual(bank.audit("ore", 300), 6)

    def test_stock_equals_audit_net_per_item(self):
        bank = GuildBank(quota_per_day=100)
        bank.deposit("op-1", "p", "ore", 10, 0)
        bank.deposit("op-2", "p", "gem", 3, 0)
        bank.withdraw("op-3", "p", "ore", 4, 100)
        for item in ("ore", "gem"):
            self.assertEqual(bank.stock[item], bank.audit(item, 200))


class LogTrimTest(unittest.TestCase):
    def test_log_bounded_and_audit_still_consistent(self):
        bank = GuildBank(quota_per_day=1000, log_limit=10)
        for index in range(50):
            bank.deposit("op-d%d" % index, "p", "ore", 2, index)
        self.assertLessEqual(len(bank.log), 10)
        self.assertEqual(bank.stock["ore"], 100)
        self.assertEqual(bank.audit("ore", 100), 100)
        for index in range(30):
            bank.withdraw("op-w%d" % index, "p", "ore", 1, 200 + index)
        self.assertLessEqual(len(bank.log), 10)
        self.assertEqual(bank.stock["ore"], 70)
        self.assertEqual(bank.audit("ore", 300), 70)


class ScanTest(unittest.TestCase):
    def test_audit_does_not_scan_log(self):
        bank = GuildBank(quota_per_day=100000, log_limit=100000)
        for index in range(3000):
            bank.deposit("op-%d" % index, "p", "ore", 1, index)
        for _ in range(3000):
            bank.audit("ore", 0)
        self.assertLessEqual(bank.scanned_count(), 3000)


class ReplayDeterminismTest(unittest.TestCase):
    def test_same_sequence_same_result(self):
        def run():
            bank = GuildBank(quota_per_day=5, log_limit=4)
            results = []
            ops = [
                ("d", "op-1", "pa", "ore", 9, 0),
                ("w", "op-2", "pa", "ore", 3, 10),
                ("d", "op-1", "pa", "ore", 9, 20),
                ("w", "op-2", "pa", "ore", 3, 30),
                ("w", "op-3", "pa", "ore", 9, 40),
                ("d", "op-4", "pb", "gem", 2, 50),
            ]
            for kind, op_id, player, item, count, now_ms in ops:
                if kind == "d":
                    results.append(bank.deposit(op_id, player, item, count, now_ms))
                else:
                    results.append(bank.withdraw(op_id, player, item, count, now_ms))
            return results, dict(bank.stock), bank.audit("ore", 60), bank.audit("gem", 60)

        self.assertEqual(run(), run())


class ReferenceBank:
    """参考实现：幂等台账 + 额度校验 + 全量事件重放的净变化（不裁剪、审计重扫）。"""

    def __init__(self, quota_per_day):
        self.quota_per_day = quota_per_day
        self.stock = {}
        self.events = []
        self.daily = {}
        self.handled = set()

    def deposit(self, op_id, player, item, count, now_ms):
        if op_id in self.handled:
            return False
        self.handled.add(op_id)
        self.stock[item] = self.stock.get(item, 0) + count
        self.events.append((item, count))
        return True

    def withdraw(self, op_id, player, item, count, now_ms):
        if op_id in self.handled:
            return 0
        day_key = (player, now_ms // MS_PER_DAY)
        if self.daily.get(day_key, 0) + count > self.quota_per_day:
            return 0
        if self.stock.get(item, 0) < count:
            return 0
        self.handled.add(op_id)
        self.daily[day_key] = self.daily.get(day_key, 0) + count
        self.stock[item] -= count
        self.events.append((item, -count))
        return count

    def audit(self, item):
        net = 0
        for name, delta in self.events:
            if name == item:
                net += delta
        return net


class ReferenceComparisonTest(unittest.TestCase):
    def test_random_sequences_match_reference(self):
        rng = random.Random(20260930)
        players = ["pa", "pb", "pc"]
        items = ["ore", "gem"]
        for _ in range(200):
            quota = rng.randint(1, 20)
            log_limit = rng.randint(1, 8)
            bank = GuildBank(quota_per_day=quota, log_limit=log_limit)
            ref = ReferenceBank(quota_per_day=quota)
            op_ids = ["op-%d" % i for i in range(40)]
            for _ in range(60):
                op_id = rng.choice(op_ids)
                player = rng.choice(players)
                item = rng.choice(items)
                now_ms = rng.randint(0, 3) * MS_PER_DAY + rng.randint(0, 999)
                kind = rng.choice(["deposit", "withdraw", "over_quota"])
                if kind == "deposit":
                    count = rng.randint(1, 30)
                    got = bank.deposit(op_id, player, item, count, now_ms)
                    want = ref.deposit(op_id, player, item, count, now_ms)
                else:
                    if kind == "over_quota":
                        count = quota + rng.randint(1, 5)
                    else:
                        count = rng.randint(1, 30)
                    got = bank.withdraw(op_id, player, item, count, now_ms)
                    want = ref.withdraw(op_id, player, item, count, now_ms)
                self.assertEqual(got, want)
                self.assertEqual(bank.stock, ref.stock)
                for name in items:
                    self.assertEqual(bank.audit(name, now_ms), ref.audit(name))
                self.assertLessEqual(len(bank.log), log_limit)


if __name__ == "__main__":
    unittest.main()
