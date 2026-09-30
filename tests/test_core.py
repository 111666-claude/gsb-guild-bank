import unittest

from guildbank.core import GuildBank


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


if __name__ == "__main__":
    unittest.main()
