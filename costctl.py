#!/usr/bin/env python3
"""costctl — small CLI to manage AWS cost-related resources.

W6 XBrain side challenge starter. Fork this repo, customize for your group,
then submit per the W6 announcement.

Usage:
    ./costctl.py <command> [options]
    ./costctl.py --help
"""
import argparse
import os
import sys


def build_parser():
    p = argparse.ArgumentParser(
        prog="costctl",
        description="Manage AWS cost-related resources (XBrain W6 side challenge).",
    )
    p.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1",
        help="AWS region (default: $AWS_REGION or us-east-1)",
    )
    sub = p.add_subparsers(dest="command", required=True, metavar="<command>")

    # ---- core: list ----
    ls = sub.add_parser("list", help="list resources, filter by tag / missing-tag")
    ls.add_argument("type", choices=["ec2", "rds", "s3", "volume"])
    ls.add_argument(
        "--tag", action="append", default=[], metavar="key=value",
        help="filter resources matching this tag (repeatable)",
    )
    ls.add_argument(
        "--missing-tag", action="append", default=[], metavar="key",
        help="filter resources missing this tag key (repeatable)",
    )

    # ---- core: cost ----
    c = sub.add_parser("cost", help="show cost of resources matching tag")
    c.add_argument(
        "--tag", required=True, metavar="key=value",
        help="e.g. Application=HealthBot",
    )
    c.add_argument("--days", type=int, default=7)

    # ---- core: terminate ----
    t = sub.add_parser("terminate", help="terminate/delete one resource (asks confirmation)")
    t.add_argument("type", choices=["ec2", "rds", "s3", "volume"])
    t.add_argument("--id", required=True)
    t.add_argument("--force", action="store_true", help="skip y/N confirmation")

    # ---- core: tag ----
    tg = sub.add_parser("tag", help="add/update tags on one resource")
    tg.add_argument("type", choices=["ec2", "rds", "s3", "volume"])
    tg.add_argument("--id", required=True)
    tg.add_argument(
        "--set", action="append", required=True, metavar="key=value",
        help="repeatable: --set Owner=alice --set Application=HealthBot",
    )

    # ---- stretch: clean ----
    cl = sub.add_parser("clean", help="(stretch) bulk terminate resources by tag")
    cl.add_argument("--tag", required=True, metavar="key=value")
    cl.add_argument("--apply", action="store_true", help="default is dry-run")

    # ---- stretch: idle ----
    idl = sub.add_parser("idle", help="(stretch) find idle EC2 by CPU avg")
    idl.add_argument("--threshold", type=float, default=5.0, metavar="CPU_PERCENT")
    idl.add_argument("--hours", type=int, default=24)

    # ---- stretch: migrate-gp3 ----
    m = sub.add_parser("migrate-gp3", help="(stretch) gp2 -> gp3 EBS migration")
    m.add_argument("--apply", action="store_true", help="default is dry-run")
    m.add_argument("--volume-id", help="restrict apply to this volume")

    return p


CMD_MODULE = {
    "list": "list_cmd",
    "cost": "cost_cmd",
    "terminate": "terminate_cmd",
    "tag": "tag_cmd",
    "clean": "clean_cmd",
    "idle": "idle_cmd",
    "migrate-gp3": "migrate_gp3_cmd",
}


def main():
    args = build_parser().parse_args()
    os.environ["AWS_REGION"] = args.region
    os.environ["AWS_DEFAULT_REGION"] = args.region

    module_name = CMD_MODULE[args.command]
    module = __import__(f"commands.{module_name}", fromlist=["run"])
    try:
        module.run(args)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
