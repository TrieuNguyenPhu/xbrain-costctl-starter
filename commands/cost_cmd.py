"""cost — show cost of resources matching a tag, over the last N days.

WHAT YOU MUST BUILD
-------------------
A function that:
  1. Queries Cost Explorer (`ce.get_cost_and_usage`) for the last N days
  2. Filters by a tag (e.g. Application=HealthBot)
  3. Groups by SERVICE dimension
  4. Sums per-service costs across the date range
  5. Prints services sorted descending by cost, plus a TOTAL row

HELPERS YOU CAN USE
-------------------
From commands._common:
  parse_kv(s) -> (k, v)             # "Application=HealthBot" -> tuple

AWS APIS YOU'LL NEED
--------------------
ce = boto3.client("ce")
ce.get_cost_and_usage(
    TimePeriod={"Start": "YYYY-MM-DD", "End": "YYYY-MM-DD"},
    Granularity="DAILY",
    Metrics=["UnblendedCost"],
    Filter={"Tags": {"Key": "<tag_key>", "Values": ["<tag_value>"]}},
    GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
)

The response has `ResultsByTime` (one entry per day), each with `Groups` —
each group has `Keys=[service_name]` and `Metrics={"UnblendedCost":{"Amount":"1.23"}}`.

EXPECTED OUTPUT FORMAT
----------------------
    Cost for Application=HealthBot over last 7 days (2026-05-14 → 2026-05-21):
    ------------------------------------------------------------
      Amazon Elastic Compute Cloud - Compute        $    8.42
      Amazon Relational Database Service             $    5.18
      ...
    ------------------------------------------------------------
      TOTAL                                          $   13.80

GOTCHAS
-------
- Cost data lags 8–24h. If --days 1 returns nothing, try --days 7.
- Tag filter requires that you have ACTIVATED cost allocation tags in Billing.
- Amount field is a STRING in the response — cast to float before summing.

VERIFY MANUALLY (no test file for this command)
-----------------------------------------------
    ./costctl.py cost --tag Application=<your-app> --days 7

The first time you run this, double-check against the AWS Console
(Cost Management → Cost Explorer → filter by same tag + same range).
Output should match within a few cents.
"""
import boto3
from collections import defaultdict
from datetime import date, timedelta

from commands._common import parse_kv


def run(args):
    """Entry point.

    Args set by argparse:
        args.tag   — "key=value" string (REQUIRED)
        args.days  — int, default 7
    """
    tag_key, tag_val = parse_kv(args.tag)

    # ── Tính khoảng thời gian ──────────────────────────────────────────────────
    end_date   = date.today()
    start_date = end_date - timedelta(days=args.days)
    start_str  = start_date.strftime("%Y-%m-%d")
    end_str    = end_date.strftime("%Y-%m-%d")

    # ── Gọi Cost Explorer ──────────────────────────────────────────────────────
    ce = boto3.client("ce")
    response = ce.get_cost_and_usage(
        TimePeriod={"Start": start_str, "End": end_str},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        Filter={"Tags": {"Key": tag_key, "Values": [tag_val]}},
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )

    # ── Tổng hợp chi phí theo service (cộng dồn nhiều ngày) ───────────────────
    totals: dict[str, float] = defaultdict(float)
    for day in response.get("ResultsByTime", []):
        for group in day.get("Groups", []):
            service = group["Keys"][0]
            amount  = float(group["Metrics"]["UnblendedCost"]["Amount"])
            totals[service] += amount

    # ── Loại bỏ service có chi phí = 0 ────────────────────────────────────────
    totals = {k: v for k, v in totals.items() if v > 0}

    # ── In kết quả ────────────────────────────────────────────────────────────
    separator = "-" * 62
    print(f"Cost for {tag_key}={tag_val} over last {args.days} days "
          f"({start_str} -> {end_str}):")
    print(separator)

    if not totals:
        print("  (no cost data found — cost data may lag 8–24h)")
    else:
        # Sắp xếp giảm dần theo chi phí
        sorted_services = sorted(totals.items(), key=lambda x: x[1], reverse=True)
        for service, amount in sorted_services:
            print(f"  {service:<48}  ${amount:>8.2f}")

    print(separator)
    grand_total = sum(totals.values())
    print(f"  {'TOTAL':<48}  ${grand_total:>8.2f}")
