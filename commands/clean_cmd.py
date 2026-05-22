"""clean — (stretch) bulk terminate resources matching a tag.

WARNING — DESIGN-FOR-SAFETY
---------------------------
This is the most dangerous command in the CLI. Get the contract right:

  1. DEFAULT IS DRY-RUN. Without --apply the command MUST NOT touch resources.
     It only lists what WOULD be deleted.
  2. Even with --apply, you should consider printing a summary count first
     ("about to terminate N EC2 + M volumes — proceed?"), though for this
     starter a hard `--apply` flag is enough.
  3. Never use this with a tag you don't fully own. Reflection prompt in
     README covers the blast-radius scenario.

WHAT YOU MUST BUILD
-------------------
1. `_find_targets(tag_key, tag_val)` — return a dict like:
     {"ec2": [<instance ids in non-terminal state>],
      "volume": [<volume ids in 'available' state only>]}
   Skip terminated/shutting-down instances (already gone).
   Skip in-use volumes (can't delete while attached — would error anyway).

2. `run(args)` — call _find_targets, print the plan, then either:
     - bail with "(dry-run — pass --apply to ...)"  (default)
     - or actually terminate (when --apply)

HELPERS YOU CAN USE
-------------------
From commands._common:
  parse_kv(s) -> (k, v)

AWS APIS YOU'LL NEED
--------------------
- ec2.describe_instances() + describe_volumes() — same as list_cmd
- ec2.terminate_instances(InstanceIds=[...])
- ec2.delete_volume(VolumeId=...)  (per volume, no bulk API)

VERIFY
------
    pytest tests/test_clean.py -v
"""
import boto3

from commands._common import parse_kv

# Các trạng thái instance đã xem như "đã xong" — không cần terminate thêm
_TERMINAL_STATES = {"terminated", "shutting-down"}


def _find_targets(tag_key, tag_val):
    """Return {"ec2": [...], "volume": [...]} matching tag in non-terminal state.

    Chỉ trả về:
    - EC2 instance: trạng thái KHÔNG phải terminal (running, stopped, pending, ...)
    - EBS volume:   trạng thái 'available' (không đang gắn vào instance nào)
    """
    ec2 = boto3.client("ec2")

    # ── Tìm EC2 instances ──────────────────────────────────────────────────────
    ec2_ids = []
    tag_filter = [{"Name": f"tag:{tag_key}", "Values": [tag_val]}]

    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate(Filters=tag_filter):
        for reservation in page["Reservations"]:
            for instance in reservation["Instances"]:
                state = instance["State"]["Name"]
                if state not in _TERMINAL_STATES:
                    ec2_ids.append(instance["InstanceId"])

    # ── Tìm EBS volumes ────────────────────────────────────────────────────────
    volume_ids = []
    vol_paginator = ec2.get_paginator("describe_volumes")
    for page in vol_paginator.paginate(Filters=tag_filter):
        for volume in page["Volumes"]:
            # Chỉ lấy volume ở trạng thái 'available' (chưa gắn vào instance)
            if volume["State"] == "available":
                volume_ids.append(volume["VolumeId"])

    return {"ec2": ec2_ids, "volume": volume_ids}


def run(args):
    """Entry point.

    Args set by argparse:
        args.tag    — "key=value" string (REQUIRED)
        args.apply  — bool, must be True to actually delete (default False = dry-run)
    """
    tag_key, tag_val = parse_kv(args.tag)
    targets = _find_targets(tag_key, tag_val)

    ec2_ids    = targets["ec2"]
    volume_ids = targets["volume"]
    total      = len(ec2_ids) + len(volume_ids)

    # ── Không tìm thấy gì ──────────────────────────────────────────────────────
    if total == 0:
        print("Nothing to clean.")
        return

    # ── In kế hoạch xóa ───────────────────────────────────────────────────────
    separator = "-" * 78
    print(f"Resources matching {args.tag}:")
    print(separator)
    for iid in ec2_ids:
        print(f"  EC2      {iid}")
    for vid in volume_ids:
        print(f"  volume   {vid}")
    print(separator)
    print(f"  Total: {len(ec2_ids)} EC2 instance(s), {len(volume_ids)} volume(s)")

    # ── Dry-run: không làm gì, chỉ thông báo ──────────────────────────────────
    if not args.apply:
        print(f"\n(dry-run — pass --apply to actually terminate {total} resource(s))")
        return

    # ── Apply: thực sự terminate ───────────────────────────────────────────────
    ec2 = boto3.client("ec2")

    # Terminate toàn bộ EC2 instances một lần (API hỗ trợ bulk)
    if ec2_ids:
        ec2.terminate_instances(InstanceIds=ec2_ids)
        for iid in ec2_ids:
            print(f"Terminated EC2 {iid}")

    # Delete từng EBS volume (không có bulk API)
    for vid in volume_ids:
        ec2.delete_volume(VolumeId=vid)
        print(f"Deleted volume {vid}")
