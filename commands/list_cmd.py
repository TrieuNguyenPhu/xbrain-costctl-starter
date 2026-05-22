"""list — list AWS resources by type, filter by tag / missing-tag.

WHAT YOU MUST BUILD
-------------------
Support 4 resource types: ec2, rds, s3, volume.
Each takes:
- `want` — list of (key, value) tag pairs the resource MUST have
- `missing` — list of tag keys the resource MUST NOT have

Print a formatted table to stdout. Test cases are in tests/test_list.py.

HELPERS YOU CAN USE
-------------------
From commands._common:
  parse_kv(s) -> (k, v)            # "Owner=alice" -> ("Owner", "alice")
  tags_to_dict(items) -> dict       # boto3 [{"Key","Value"}] -> {k: v}
  tags_match(tags, want, missing) -> bool

AWS APIS YOU'LL NEED
--------------------
- EC2: ec2.describe_instances() with get_paginator
- RDS: rds.describe_db_instances(), then list_tags_for_resource(ResourceName=arn)
- S3:  s3.list_buckets(), then get_bucket_tagging(Bucket=name)
       (catch ClientError when bucket has no tagging config — treat as {})
- EBS: ec2.describe_volumes() with get_paginator

EXPECTED OUTPUT FORMAT (when run from CLI)
------------------------------------------
    EC2 Environment=dev — 1 found:
    ------------------------------------------------------------------------------
      i-0abc123def456789a       t3.micro       running       Environment=dev

VERIFY
------
    pytest tests/test_list.py -v
"""
import boto3
from botocore.exceptions import ClientError

from commands._common import parse_kv, tags_to_dict, tags_match


def _list_ec2(want, missing):
    """List EC2 instances matching tag filters.

    Args:
        want: list of (key, value) tag pairs that must all match
        missing: list of tag keys that must NOT be present

    Returns:
        list of (instance_id, instance_type, state, tags_dict) tuples
    """
    ec2 = boto3.client("ec2")
    paginator = ec2.get_paginator("describe_instances")

    rows = []
    for page in paginator.paginate():
        for reservation in page["Reservations"]:
            for instance in reservation["Instances"]:
                # Bỏ qua các instance đã bị terminated
                state = instance["State"]["Name"]
                if state == "terminated":
                    continue

                tags = tags_to_dict(instance.get("Tags", []))
                if tags_match(tags, want, missing):
                    rows.append((
                        instance["InstanceId"],
                        instance.get("InstanceType", "unknown"),
                        state,
                        tags,
                    ))
    return rows


def _list_rds(want, missing):
    """Same shape as _list_ec2 but for RDS DB instances.

    Note: RDS tags require a separate API call per DB:
        rds.list_tags_for_resource(ResourceName=db['DBInstanceArn'])

    Returns:
        list of (db_id, db_class, db_status, tags_dict) tuples
    """
    rds = boto3.client("rds")
    rows = []

    paginator = rds.get_paginator("describe_db_instances")
    for page in paginator.paginate():
        for db in page["DBInstances"]:
            # Lấy tag bằng cách gọi riêng với ARN
            arn = db["DBInstanceArn"]
            tag_list = rds.list_tags_for_resource(ResourceName=arn).get("TagList", [])
            tags = tags_to_dict(tag_list)

            if tags_match(tags, want, missing):
                rows.append((
                    db["DBInstanceIdentifier"],
                    db.get("DBInstanceClass", "unknown"),
                    db.get("DBInstanceStatus", "unknown"),
                    tags,
                ))
    return rows


def _list_s3(want, missing):
    """List S3 buckets matching tag filters.

    Note: get_bucket_tagging raises ClientError if no tagging config exists
    for that bucket. Treat that as an empty tags dict, not an error.

    Returns:
        list of (bucket_name, "bucket", "active", tags_dict) tuples
    """
    s3 = boto3.client("s3")
    buckets = s3.list_buckets().get("Buckets", [])

    rows = []
    for bucket in buckets:
        name = bucket["Name"]

        # Lấy tag của bucket; bỏ qua lỗi nếu bucket chưa có tag nào
        try:
            tag_list = s3.get_bucket_tagging(Bucket=name).get("TagSet", [])
        except ClientError:
            tag_list = []

        tags = tags_to_dict(tag_list)
        if tags_match(tags, want, missing):
            rows.append((name, "bucket", "active", tags))

    return rows


def _list_volume(want, missing):
    """List EBS volumes matching tag filters.

    Returns:
        list of (volume_id, "<type>-<size>GB", state, tags_dict) tuples
        e.g. ("vol-0abc", "gp2-100GB", "in-use", {"purpose": "practice"})
    """
    ec2 = boto3.client("ec2")
    paginator = ec2.get_paginator("describe_volumes")

    rows = []
    for page in paginator.paginate():
        for volume in page["Volumes"]:
            tags = tags_to_dict(volume.get("Tags", []))
            if tags_match(tags, want, missing):
                vol_type = volume.get("VolumeType", "unknown")
                size = volume.get("Size", 0)
                type_size = f"{vol_type}-{size}GB"

                rows.append((
                    volume["VolumeId"],
                    type_size,
                    volume.get("State", "unknown"),
                    tags,
                ))
    return rows


DISPATCH = {
    "ec2": _list_ec2,
    "rds": _list_rds,
    "s3": _list_s3,
    "volume": _list_volume,
}


def run(args):
    """Entry point called by costctl.py.

    Steps you should perform:
      1. Convert args.tag (list of "k=v" strings) → want pairs via parse_kv
      2. Use args.missing_tag (list of keys) as-is
      3. Call DISPATCH[args.type](want, missing) → rows
      4. Print a header line, separator, then one row per resource

    Args set by argparse:
        args.type         — one of "ec2", "rds", "s3", "volume"
        args.tag          — list[str], each "key=value"
        args.missing_tag  — list[str], each "key"
    """
    # 1. Parse tag filters
    want = [parse_kv(t) for t in args.tag]
    missing = list(args.missing_tag)

    # 2. Gọi hàm dispatch phù hợp với resource type
    rows = DISPATCH[args.type](want, missing)

    # 3. Xây dựng tiêu đề header
    tag_label = ", ".join(f"{k}={v}" for k, v in want)
    missing_label = ", ".join(f"!{k}" for k in missing)
    filters = " ".join(filter(None, [tag_label, missing_label]))
    header_filter = f" {filters}" if filters else ""

    resource_type = args.type.upper()
    header = f"{resource_type}{header_filter} — {len(rows)} found:"
    separator = "-" * 78

    # 4. In kết quả
    print(header)
    print(separator)
    for resource_id, resource_type_info, state, tags in rows:
        tags_str = ", ".join(f"{k}={v}" for k, v in tags.items())
        print(f"  {resource_id:<30}  {resource_type_info:<15}  {state:<15}  {tags_str}")
