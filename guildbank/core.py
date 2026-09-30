"""公会仓库：库存守恒、每日额度、提交幂等、审计日志有界。

实现要点：
- 提交幂等：生效过的 op_id 记入 handled，重复提交直接拒绝，库存、额度与日志都不再变。
- 每日额度：按 (玩家, 服务日) 累计取出量，超过 quota_per_day 拒绝。
- 库存守恒：取出先扣库存，库存不足拒绝；net 索引按物品维护净变化，恒等于 stock。
- 日志有界：deque(maxlen=log_limit) 自动丢最旧，审计走 net 索引，单次 O(1) 摊还。
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
        self.handled = set()
        self.net = {}
        self.scanned = 0

    def _check_count(self, count):
        if count <= 0:
            raise BankError("数量必须为正整数: %r" % (count,))

    def deposit(self, op_id, player, item, count, now_ms):
        """存入物品。同一 op_id 只生效一次，重复提交返回 False。"""
        self._check_count(count)
        if op_id in self.handled:
            return False
        self.handled.add(op_id)
        self.stock[item] = self.stock.get(item, 0) + count
        self.net[item] = self.net.get(item, 0) + count
        self.log.append((op_id, player, item, count, now_ms))
        return True

    def withdraw(self, op_id, player, item, count, now_ms):
        """取出物品。重复提交、超每日额度或库存不足时拒绝并返回 0。"""
        self._check_count(count)
        if op_id in self.handled:
            return 0
        day = now_ms // MS_PER_DAY
        key = (player, day)
        if self.daily.get(key, 0) + count > self.quota_per_day:
            return 0
        if self.stock.get(item, 0) < count:
            return 0
        self.handled.add(op_id)
        self.daily[key] = self.daily.get(key, 0) + count
        self.stock[item] -= count
        self.net[item] = self.net.get(item, 0) - count
        self.log.append((op_id, player, item, -count, now_ms))
        return count

    def audit(self, item, now_ms):
        """审计某物品的净变化。走按物品维护的净变化索引，单次 O(1)。"""
        self.scanned += 1
        return self.net.get(item, 0)

    def scanned_count(self):
        return self.scanned
