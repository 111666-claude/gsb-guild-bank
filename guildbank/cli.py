"""命令行入口：跑公会仓库样例。"""

import argparse

from .core import GuildBank


def build_parser():
    parser = argparse.ArgumentParser(prog="guild-bank", description="公会仓库")
    parser.add_argument("--sample", default="duplicate", help="duplicate / quota / conserve / scan")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.sample == "duplicate":
        bank = GuildBank()
        bank.deposit("op-1", "p", "ore", 5, 0)
        second = bank.deposit("op-1", "p", "ore", 5, 10)
        print("second=%s stock=%d" % (str(second).lower(), bank.stock.get("ore", 0)))
    elif args.sample == "quota":
        bank = GuildBank(quota_per_day=10)
        bank.deposit("op-1", "p", "ore", 50, 0)
        taken = bank.withdraw("op-2", "p", "ore", 15, 100)
        print("taken=%d" % taken)
    elif args.sample == "conserve":
        bank = GuildBank(quota_per_day=100)
        bank.deposit("op-1", "p", "ore", 10, 0)
        bank.withdraw("op-2", "p", "ore", 4, 100)
        bank.withdraw("op-3", "p", "ore", 20, 200)
        print("net=%d stock=%d" % (bank.audit("ore", 300), bank.stock.get("ore", 0)))
    elif args.sample == "scan":
        bank = GuildBank(quota_per_day=100000, log_limit=100000)
        for index in range(3000):
            bank.deposit("op-%d" % index, "p", "ore", 1, index)
        for _ in range(3000):
            bank.audit("ore", 0)
        print("scanned=%d" % bank.scanned_count())
    else:
        raise SystemExit("需要 --sample duplicate|quota|conserve|scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
