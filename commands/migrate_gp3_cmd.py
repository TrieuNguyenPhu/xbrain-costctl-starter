"""migrate-gp3 — (stretch) plan or apply gp2 → gp3 EBS migration.

WHY THIS MATTERS
----------------
gp3 is cheaper than gp2 ($0.08 vs $0.10 per GB-month) AND faster
(3000 IOPS baseline vs 3 IOPS/GB scaling). Most gp2 volumes should migrate.
EBS supports live modification — no downtime, no detach.

WHAT YOU MUST BUILD
-------------------
1. Dry-run mode (default):
   - List all gp2 volumes in the account
   - Show size, attached instance, and projected monthly savings per volume
   - Print total savings if all migrated

2. Apply mode (--apply):
   - With --volume-id: migrate just that one
   - Without --volume-id: migrate ALL gp2 volumes
   - Use ec2.modify_volume(...) — the modification runs in the background

AWS APIS YOU'LL NEED
--------------------
ec2.describe_volumes(Filters=[{"Name": "volume-type", "Values": ["gp2"]}])
ec2.modify_volume(
    VolumeId=vid,
    VolumeType="gp3",
    Iops=3000,        # baseline included free
    Throughput=125,   # baseline included free
)

After calling modify_volume, the volume goes through state transitions:
    in-use → modifying → optimizing → in-use (now gp3)
The app stays online throughout. Optimization takes ~30 min for a 100GB
volume; longer for larger volumes.

EXPECTED OUTPUT FORMAT (dry-run)
--------------------------------
    gp2 volumes (price delta $0.020/GB-month):
    ------------------------------------------------------------------------------
      vol-0abc123def456789a    100GB  attached=i-0aaa            $2.00/mo savings
      vol-0bbb456ef789012345     50GB  attached=(none)            $1.00/mo savings
    ------------------------------------------------------------------------------

    (dry-run — pass --apply --volume-id <id> to migrate one, or --apply to migrate ALL)

EXPECTED OUTPUT FORMAT (apply)
------------------------------
      → modify_volume issued for vol-0abc123def456789a (gp3, 3000 IOPS, 125 MiB/s)

    Volume(s) entering 'modifying' → 'optimizing' state. App stays online.
    Use `costctl list volume` after ~30 minutes to confirm 'in-use' + gp3.

VERIFY MANUALLY (no test file for this command)
-----------------------------------------------
    ./costctl.py migrate-gp3                           # dry-run, no side effects
    ./costctl.py migrate-gp3 --apply --volume-id vol-xxx  # migrate ONE

Pick a small volume first. Confirm via:
    ./costctl.py list volume --tag <something>
or AWS Console → EC2 → Volumes.

PRICING NOTE
------------
Constants below assume us-east-1 on-demand pricing. If your account is in
a different region, the dollar figure displayed is rough — but the migration
itself works the same anywhere.
"""
import boto3

# us-east-1 on-demand pricing per GB-month. Override if you care about exact $.
GP2_PRICE   = 0.10
GP3_PRICE   = 0.08
PRICE_DELTA = GP2_PRICE - GP3_PRICE   # $0.02/GB-month


def _get_gp2_volumes(ec2, volume_id=None):
    """Lấy danh sách volume gp2. Nếu volume_id được chỉ định thì chỉ lấy volume đó."""
    filters = [{"Name": "volume-type", "Values": ["gp2"]}]
    kwargs  = {"Filters": filters}
    if volume_id:
        kwargs["VolumeIds"] = [volume_id]

    paginator = ec2.get_paginator("describe_volumes")
    volumes   = []
    for page in paginator.paginate(**kwargs):
        volumes.extend(page["Volumes"])
    return volumes


def run(args):
    """Entry point.

    Args set by argparse:
        args.apply       — bool, default False (dry-run)
        args.volume_id   — optional str, only migrate this volume when --apply
    """
    ec2 = boto3.client("ec2")

    # Khi --apply + --volume-id thì chỉ migrate volume đó (và vẫn show dry-run cho nó)
    volumes = _get_gp2_volumes(ec2, volume_id=args.volume_id if args.apply else None)

    # Với dry-run không có --volume-id, lấy toàn bộ gp2
    if not args.apply:
        volumes = _get_gp2_volumes(ec2)

    # ── In danh sách / kế hoạch ────────────────────────────────────────────────
    separator = "-" * 78
    print(f"gp2 volumes (price delta ${PRICE_DELTA:.3f}/GB-month):")
    print(separator)

    total_savings = 0.0
    for vol in volumes:
        vid       = vol["VolumeId"]
        size_gb   = vol["Size"]
        savings   = size_gb * PRICE_DELTA

        # Xác định instance đang gắn (nếu có)
        attachments = vol.get("Attachments", [])
        attached_to = attachments[0]["InstanceId"] if attachments else "(none)"

        print(f"  {vid:<25}  {size_gb:>5}GB  attached={attached_to:<22}  "
              f"${savings:.2f}/mo savings")
        total_savings += savings

    print(separator)

    if not volumes:
        print("  (no gp2 volumes found)")
        return

    print(f"\n  Total potential savings: ${total_savings:.2f}/mo "
          f"across {len(volumes)} volume(s)")

    # ── Dry-run: dừng lại, không migrate ──────────────────────────────────────
    if not args.apply:
        print(f"\n(dry-run — pass --apply --volume-id <id> to migrate one, "
              f"or --apply to migrate ALL)")
        return

    # ── Apply: gọi modify_volume cho từng volume ───────────────────────────────
    print()
    migrated = 0
    for vol in volumes:
        vid = vol["VolumeId"]
        try:
            ec2.modify_volume(
                VolumeId=vid,
                VolumeType="gp3",
                Iops=3000,       # baseline gp3, không tính thêm phí
                Throughput=125,  # MiB/s, baseline gp3
            )
            print(f"  → modify_volume issued for {vid} (gp3, 3000 IOPS, 125 MiB/s)")
            migrated += 1
        except Exception as e:
            print(f"  ✗ Failed for {vid}: {e}")

    print(f"\nVolume(s) entering 'modifying' → 'optimizing' state. App stays online.")
    print(f"Use `./costctl.py list volume` after ~30 minutes to confirm 'in-use' + gp3.")
