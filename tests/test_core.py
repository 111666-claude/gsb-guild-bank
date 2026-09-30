"""公会仓库。"""
import random
import unittest

from guildbank.core import BankError, GuildBank, MS_PER_DAY


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
        self.assertTrue(bank.deposit("op-1", "p", "ore", 10, 0))
        self.assertFalse(bank.deposit("op-1", "p", "ore", 10, 10))
        self.assertEqual(bank.stock["ore"], 10)
        self.assertEqual(len(bank.handled), 1)
        self.assertEqual(len(bank.log), 1)
        self.assertEqual(bank.audit("ore", 20), 10)

    def test_duplicate_withdraw_returns_zero_and_changes_nothing(self):
        bank = GuildBank(quota_per_day=100)
        bank.deposit("op-1", "p", "ore", 10, 0)
        self.assertEqual(bank.withdraw("op-2", "p", "ore", 4, 100), 4)
        self.assertEqual(bank.withdraw("op-2", "p", "ore", 4, 200), 0)
        self.assertEqual(bank.stock["ore"], 6)
        self.assertEqual(bank.daily[("p", 0)], 4)
        self.assertEqual(len(bank.log), 2)

    def test_op_id_unique_across_players_and_items(self):
        bank = GuildBank()
        self.assertTrue(bank.deposit("op-1", "p", "ore", 3, 0))
        self.assertFalse(bank.deposit("op-1", "q", "ore", 3, 0))

    def test_rejected_op_can_be_retried(self):
        bank = GuildBank(quota_per_day=100)
        self.assertEqual(bank.withdraw("op-x", "p", "ore", 5, 0), 0)
        bank.deposit("op-1", "p", "ore", 5, 0)
        self.assertEqual(bank.withdraw("op-x", "p", "ore", 5, 100), 5)


class DailyQuotaTest(unittest.TestCase):
    def test_withdraw_over_quota_returns_zero(self):
        bank = GuildBank(quota_per_day=10)
        bank.deposit("op-1", "p", "ore", 50, 0)
        self.assertEqual(bank.withdraw("op-2", "p", "ore", 15, 100), 0)
        self.assertEqual(bank.stock["ore"], 50)
        self.assertEqual(len(bank.log), 1)

    def test_quota_boundary_is_inclusive(self):
        bank = GuildBank(quota_per_day=10)
        bank.deposit("op-1", "p", "ore", 50, 0)
        self.assertEqual(bank.withdraw("op-2", "p", "ore", 6, 0), 6)
        self.assertEqual(bank.withdraw("op-3", "p", "ore", 4, 0), 4)
        self.assertEqual(bank.withdraw("op-4", "p", "ore", 1, 0), 0)

    def test_quota_resets_per_service_day(self):
        bank = GuildBank(quota_per_day=10)
        bank.deposit("op-1", "p", "ore", 50, 0)
        self.assertEqual(bank.withdraw("op-2", "p", "ore", 10, 0), 10)
        self.assertEqual(bank.withdraw("op-3", "p", "ore", 1, MS_PER_DAY - 1), 0)
        self.assertEqual(bank.withdraw("op-4", "p", "ore", 1, MS_PER_DAY), 1)

    def test_quota_per_player(self):
        bank = GuildBank(quota_per_day=10)
        bank.deposit("op-1", "p", "ore", 50, 0)
        bank.deposit("op-2", "q", "ore", 50, 0)
        self.assertEqual(bank.withdraw("op-3", "p", "ore", 10, 0), 10)
        self.assertEqual(bank.withdraw("op-4", "q", "ore", 10, 0), 10)


class ConservationTest(unittest.TestCase):
    def test_withdraw_deducts_stock_and_net_matches(self):
        bank = GuildBank(quota_per_day=100)
        bank.deposit("op-1", "p", "ore", 10, 0)
        bank.withdraw("op-2", "p", "ore", 4, 100)
        self.assertEqual(bank.stock["ore"], 6)
        self.assertEqual(bank.audit("ore", 200), 6)

    def test_insufficient_stock_returns_zero(self):
        bank = GuildBank(quota_per_day=100)
        bank.deposit("op-1", "p", "ore", 10, 0)
        self.assertEqual(bank.withdraw("op-2", "p", "ore", 20, 100), 0)
        self.assertEqual(bank.stock["ore"], 10)
        self.assertEqual(bank.audit("ore", 200), 10)

    def test_net_equals_stock_for_every_item(self):
        bank = GuildBank(quota_per_day=100)
        bank.deposit("op-1", "p", "ore", 10, 0)
        bank.deposit("op-2", "p", "wood", 8, 0)
        bank.withdraw("op-3", "p", "ore", 4, 100)
        bank.withdraw("op-4", "p", "wood", 3, 200)
        for item in ("ore", "wood", "gem"):
            self.assertEqual(bank.audit(item, 0), bank.stock.get(item, 0))

    def test_nonpositive_count_raises(self):
        bank = GuildBank()
        with self.assertRaises(BankError):
            bank.deposit("op-1", "p", "ore", 0, 0)


class LogLimitTest(unittest.TestCase):
    def test_log_drops_oldest_but_net_stays_consistent(self):
        bank = GuildBank(quota_per_day=1000, log_limit=5)
        for index in range(12):
            self.assertTrue(bank.deposit("op-%d" % index, "p", "ore", 1, index))
        self.assertEqual(len(bank.log), 5)
        self.assertEqual(bank.log[0][0], "op-7")
        self.assertEqual(bank.stock["ore"], 12)
        self.assertEqual(bank.audit("ore", 0), 12)

    def test_log_bounded_under_mixed_ops(self):
        bank = GuildBank(quota_per_day=1000, log_limit=10)
        bank.deposit("op-0", "p", "ore", 100, 0)
        for index in range(1, 40):
            bank.withdraw("op-w%d" % index, "p", "ore", 1, index)
        self.assertLessEqual(len(bank.log), 10)
        self.assertEqual(bank.audit("ore", 0), bank.stock["ore"])

    def test_replay_same_sequence_gives_same_result(self):
        def run():
            bank = GuildBank(quota_per_day=10, log_limit=5)
            results = []
            ops = [
                ("d", "op-1", "p", "ore", 10, 0),
                ("d", "op-1", "p", "ore", 10, 1),
                ("w", "op-2", "p", "ore", 6, 2),
                ("w", "op-3", "p", "ore", 6, 3),
                ("w", "op-2", "p", "ore", 6, 4),
                ("w", "op-4", "p", "ore", 1, 5),
            ]
            for kind, *rest in ops:
                op_id, player, item, count, now_ms = rest
                if kind == "d":
                    results.append(bank.deposit(op_id, player, item, count, now_ms))
                else:
                    results.append(bank.withdraw(op_id, player, item, count, now_ms))
            results.append(bank.stock.get("ore", 0))
            results.append(bank.audit("ore", 0))
            return results
        self.assertEqual(run(), run())


class ScanScaleTest(unittest.TestCase):
    def test_scanned_independent_of_log_length(self):
        bank = GuildBank(quota_per_day=100000, log_limit=100000)
        for index in range(3000):
            bank.deposit("op-%d" % index, "p", "ore", 1, index)
        bank.audit("ore", 0)
        self.assertLessEqual(bank.scanned_count(), 1)


class ReferenceBank:
    """参考实现：幂等台账 + 额度校验 + 全量台账净变化，故意用最简单的 O(n) 写法。

    台账不裁剪：净变化是全部已生效操作之和，与日志保留多少条无关。
    """

    def __init__(self, quota_per_day, log_limit):
        self.quota_per_day = quota_per_day
        self.log_limit = log_limit
        self.stock = {}
        self.ledger = []
        self.daily = {}
        self.handled = set()

    def deposit(self, op_id, player, item, count, now_ms):
        if op_id in self.handled:
            return False
        self.handled.add(op_id)
        self.stock[item] = self.stock.get(item, 0) + count
        self.ledger.append((op_id, player, item, count, now_ms))
        return True

    def withdraw(self, op_id, player, item, count, now_ms):
        if op_id in self.handled:
            return 0
        key = (player, now_ms // MS_PER_DAY)
        if self.daily.get(key, 0) + count > self.quota_per_day:
            return 0
        if self.stock.get(item, 0) < count:
            return 0
        self.handled.add(op_id)
        self.daily[key] = self.daily.get(key, 0) + count
        self.stock[item] -= count
        self.ledger.append((op_id, player, item, -count, now_ms))
        return count

    def audit(self, item):
        return sum(delta for _, _, name, delta, _ in self.ledger if name == item)


class DifferentialTest(unittest.TestCase):
    def test_200_random_sequences_match_reference(self):
        rng = random.Random(20260930)
        for _ in range(200):
            quota = rng.randint(1, 15)
            log_limit = rng.randint(1, 20)
            bank = GuildBank(quota_per_day=quota, log_limit=log_limit)
            ref = ReferenceBank(quota, log_limit)
            items = ["ore", "wood", "gem"]
            players = ["p", "q"]
            op_serial = [0]

            def new_op_id():
                op_serial[0] += 1
                return "op-%d" % op_serial[0]

            for _ in range(rng.randint(5, 40)):
                player = rng.choice(players)
                item = rng.choice(items)
                count = rng.randint(1, 20)
                now_ms = rng.randint(0, MS_PER_DAY * 3)
                kind = rng.choice(("deposit", "withdraw", "dup_deposit", "dup_withdraw"))
                if kind in ("deposit", "withdraw"):
                    op_id = new_op_id()
                    if kind == "deposit":
                        got = bank.deposit(op_id, player, item, count, now_ms)
                        want = ref.deposit(op_id, player, item, count, now_ms)
                    else:
                        got = bank.withdraw(op_id, player, item, count, now_ms)
                        want = ref.withdraw(op_id, player, item, count, now_ms)
                    self.assertEqual(got, want)
                else:
                    if kind == "dup_deposit":
                        got = bank.deposit("op-1", player, item, count, now_ms)
                        want = ref.deposit("op-1", player, item, count, now_ms)
                    else:
                        got = bank.withdraw("op-2", player, item, count, now_ms)
                        want = ref.withdraw("op-2", player, item, count, now_ms)
                    self.assertEqual(got, want)
                self.assertLessEqual(len(bank.log), log_limit)

            for item in items:
                self.assertEqual(bank.audit(item, 0), ref.audit(item))
                self.assertEqual(bank.audit(item, 0), bank.stock.get(item, 0))


if __name__ == "__main__":
    unittest.main()
