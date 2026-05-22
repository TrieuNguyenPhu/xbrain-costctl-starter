"""Integration tests for commands/list_cmd — uses moto to mock AWS."""
import boto3
import pytest
from moto import mock_aws

from commands.list_cmd import _list_ec2, _list_s3, _list_volume


def _launch(ec2, tags=None):
    ami = ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]
    spec = []
    if tags:
        spec = [{
            "ResourceType": "instance",
            "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
        }]
    return ec2.run_instances(
        ImageId=ami, MinCount=1, MaxCount=1, InstanceType="t3.micro",
        TagSpecifications=spec,
    )["Instances"][0]["InstanceId"]


@mock_aws
def test_list_ec2_empty():
    rows = _list_ec2([], [])
    assert rows == []


@mock_aws
def test_list_ec2_no_filter_returns_all():
    ec2 = boto3.client("ec2", region_name="us-east-1")
    _launch(ec2, {"Environment": "dev"})
    _launch(ec2, {"Environment": "prod"})
    rows = _list_ec2([], [])
    assert len(rows) == 2


@mock_aws
def test_list_ec2_filter_by_tag():
    ec2 = boto3.client("ec2", region_name="us-east-1")
    _launch(ec2, {"Environment": "dev"})
    _launch(ec2, {"Environment": "prod"})
    rows = _list_ec2([("Environment", "dev")], [])
    assert len(rows) == 1
    assert rows[0][3]["Environment"] == "dev"


@mock_aws
def test_list_ec2_missing_tag():
    ec2 = boto3.client("ec2", region_name="us-east-1")
    _launch(ec2, {"Application": "HealthBot"})
    _launch(ec2, {"Environment": "dev"})  # no Application tag
    rows = _list_ec2([], ["Application"])
    assert len(rows) == 1
    assert "Application" not in rows[0][3]


@mock_aws
def test_list_ec2_combined_tag_and_missing():
    ec2 = boto3.client("ec2", region_name="us-east-1")
    _launch(ec2, {"Environment": "dev", "Owner": "alice"})
    _launch(ec2, {"Environment": "dev"})  # missing Owner
    _launch(ec2, {"Environment": "prod", "Owner": "bob"})
    # dev + missing Owner → exactly 1 match
    rows = _list_ec2([("Environment", "dev")], ["Owner"])
    assert len(rows) == 1


@mock_aws
def test_list_s3_no_tagging_treated_as_empty_tags():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="empty-tag-bucket")
    # missing-tag filter on a bucket without tagging config should still match.
    rows = _list_s3([], ["Application"])
    assert any(r[0] == "empty-tag-bucket" for r in rows)


@mock_aws
def test_list_volume_returns_type_size():
    ec2 = boto3.client("ec2", region_name="us-east-1")
    ec2.create_volume(Size=100, VolumeType="gp2", AvailabilityZone="us-east-1a",
                      TagSpecifications=[{"ResourceType": "volume",
                                          "Tags": [{"Key": "purpose", "Value": "practice"}]}])
    rows = _list_volume([("purpose", "practice")], [])
    assert len(rows) == 1
    assert "gp2-100GB" in rows[0][1]
