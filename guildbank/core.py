"""公会仓库：库存守恒、每日额度、提交幂等、审计日志有界。

缺陷：不校验每日额度、同一 op_id 重复提交会重复生效、取出不扣库存（守恒被破坏）、
审计每次全扫日志、日志不裁剪。
"""


class BankError(ValueError):
    """公会仓库操作不合法。"""


class GuildBank:
    """一个公会仓库。"""

    def __init__(self, quota_per_day=100, log_limit=200):
        self.quota_per_day = quota_per_day
        self.log_limit = log_limit
        self.stock = {}
        self.log = []
        self.daily = {}
        self.handled = {}
        self.scanned = 0

    def deposit(self, op_id, player, item, count, now_ms):
        """存入物品。缺陷：不查 op_id（重复提交会重复入库），日志也不裁剪。"""
        self.stock[item] = self.stock.get(item, 0) + count
        self.log.append((op_id, player, item, count, now_ms))
        return True

    def withdraw(self, op_id, player, item, count, now_ms):
        """取出物品。缺陷：不查每日额度、不查 op_id、也不扣库存。"""
        self.log.append((op_id, player, item, -count, now_ms))
        return count

    def audit(self, item, now_ms):
        """审计某物品的净变化。缺陷：每次全扫日志。"""
        self.scanned += len(self.log)
        net = 0
        for _, _, name, delta, _ in self.log:
            if name == item:
                net += delta
        return net

    def scanned_count(self):
        return self.scanned
