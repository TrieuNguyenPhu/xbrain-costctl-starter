"""Tests for clean_cmd dry-run vs apply behaviour."""
from types import SimpleNamespace

import boto3
import pytest
from moto import mock_aws

from commands.clean_cmd import run as clean_run, _find_targets


def _args(tag, apply_=False):
    return SimpleNamespace(tag=tag, apply=apply_)


@mock_aws
def test_find_targets_finds_tagged_instance():
    ec2 = boto3.client("ec2", region_name="us-east-1")
    ami = ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]
    ec2.run_instances(
        ImageId=ami, MinCount=1, MaxCount=1, InstanceType="t3.micro",
        TagSpecifications=[{"ResourceType": "instance",
                            "Tags": [{"Key": "purpose", "Value": "practice"}]}],
    )
    ec2.run_instances(
        ImageId=ami, MinCount=1, MaxCount=1, InstanceType="t3.micro",
        TagSpecifications=[{"ResourceType": "instance",
                            "Tags": [{"Key": "purpose", "Value": "production"}]}],
    )
    t = _find_targets("purpose", "practice")
    assert len(t["ec2"]) == 1


@mock_aws
def test_clean_dry_run_does_not_delete(capsys):
    ec2 = boto3.client("ec2", region_name="us-east-1")
    ami = ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]
    ec2.run_instances(
        ImageId=ami, MinCount=1, MaxCount=1, InstanceType="t3.micro",
        TagSpecifications=[{"ResourceType": "instance",
                            "Tags": [{"Key": "purpose", "Value": "practice"}]}],
    )
    clean_run(_args("purpose=practice", apply_=False))
    captured = capsys.readouterr()
    assert "dry-run" in captured.out
    # Instance should still be running.
    states = {
        i["InstanceId"]: i["State"]["Name"]
        for r in ec2.describe_instances()["Reservations"]
        for i in r["Instances"]
    }
    assert "running" in states.values() or "pending" in states.values()


@mock_aws
def test_clean_apply_terminates(capsys):
    ec2 = boto3.client("ec2", region_name="us-east-1")
    ami = ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]
    iid = ec2.run_instances(
        ImageId=ami, MinCount=1, MaxCount=1, InstanceType="t3.micro",
        TagSpecifications=[{"ResourceType": "instance",
                            "Tags": [{"Key": "purpose", "Value": "practice"}]}],
    )["Instances"][0]["InstanceId"]
    clean_run(_args("purpose=practice", apply_=True))
    captured = capsys.readouterr()
    assert "Terminated" in captured.out
    states = {
        i["InstanceId"]: i["State"]["Name"]
        for r in ec2.describe_instances()["Reservations"]
        for i in r["Instances"]
    }
    assert states[iid] in ("shutting-down", "terminated")


@mock_aws
def test_clean_no_matches(capsys):
    clean_run(_args("purpose=practice", apply_=True))
    captured = capsys.readouterr()
    assert "Nothing to clean" in captured.out
