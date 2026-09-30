"""公会仓库：库存守恒、每日额度、提交幂等、审计日志有界。

口径（README 为准）：
- 提交幂等：同一 op_id 只生效一次，重复提交不再改变库存、额度与日志。
- 每日额度：同一玩家每个服务日最多取出 quota_per_day，超出拒绝。
- 库存守恒：取出必须扣库存，库存不足拒绝；stock 等于该物品审计净变化。
- 日志有界：超过 log_limit 丢最旧；按物品维护净变化索引，审计 O(1) 摊还。
"""

from collections import deque

MS_PER_DAY = 86_400_000


class BankError(ValueError):
    """公会仓库操作不合法。"""


class GuildBank:
    """一个公会仓库。"""

    def __init__(self, quota_per_day=100, log_limit=200):
        self.quota_per_day = quota_per_day
        self.log_limit = log_limit
        self.stock = {}
        self.log = deque(maxlen=log_limit)
        self.daily = {}
        self.handled = {}
        self.scanned = 0
        self._net = {}

    def deposit(self, op_id, player, item, count, now_ms):
        """存入物品。同一 op_id 只生效一次，重复提交返回 False。"""
        if count <= 0:
            raise BankError("存入数量必须为正")
        if op_id in self.handled:
            return False
        self.handled[op_id] = True
        self.stock[item] = self.stock.get(item, 0) + count
        self._net[item] = self._net.get(item, 0) + count
        self.log.append((op_id, player, item, count, now_ms))
        return True

    def withdraw(self, op_id, player, item, count, now_ms):
        """取出物品。重复提交、超每日额度或库存不足时拒绝并返回 0。"""
        if count <= 0:
            raise BankError("取出数量必须为正")
        if op_id in self.handled:
            return 0
        day_key = (player, now_ms // MS_PER_DAY)
        if self.daily.get(day_key, 0) + count > self.quota_per_day:
            return 0
        if self.stock.get(item, 0) < count:
            return 0
        self.handled[op_id] = True
        self.daily[day_key] = self.daily.get(day_key, 0) + count
        self.stock[item] -= count
        self._net[item] = self._net.get(item, 0) - count
        self.log.append((op_id, player, item, -count, now_ms))
        return count

    def audit(self, item, now_ms):
        """审计某物品的净变化。按物品的净变化索引 O(1) 返回，不扫日志。"""
        return self._net.get(item, 0)

    def scanned_count(self):
        return self.scanned
