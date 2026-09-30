# guild-bank

公会仓库：库存守恒、每日额度、提交幂等、审计日志有界，只用 Python 标准库。

```
python3 -m guildbank.cli --sample duplicate
python3 -m guildbank.cli --sample quota
python3 -m guildbank.cli --sample conserve
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- **提交幂等**：同一个 `op_id` 重复提交只生效一次，第二次返回 `False`，
  库存、额度与日志都不许再变。
- **每日额度**：同一玩家每个服务日最多取出 `quota_per_day`，超出时拒绝（返回 0）且不改库存。
- **库存守恒**：取出必须扣库存；`stock[item]` 等于该物品的审计净变化，
  库存不足时拒绝而不是照发。
- **日志有界**：日志超过 `log_limit` 时丢掉最旧的，但审计净变化仍必须与库存一致
  （按物品维护净变化，不许每次重扫全量日志）。
- **规模**：单公会 200 万条操作、每秒 10 万次审计查询，单次 O(1) 摊还。

## 输出契约（不改格式）

```
second=false stock=5
taken=0
net=6 stock=6
scanned<=3000
```

## 目录

```
guildbank/core.py   库存、额度与日志
guildbank/cli.py    命令行入口
tests/              unittest 用例
```
