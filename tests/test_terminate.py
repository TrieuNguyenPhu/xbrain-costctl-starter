"""Tests for terminate_cmd safety behaviour."""
from types import SimpleNamespace

import boto3
import pytest
from moto import mock_aws

from commands.terminate_cmd import run as terminate_run


def _args(type_, id_, force=True):
    return SimpleNamespace(type=type_, id=id_, force=force)


@mock_aws
def test_terminate_ec2_with_force(capsys):
    ec2 = boto3.client("ec2", region_name="us-east-1")
    ami = ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]
    iid = ec2.run_instances(ImageId=ami, MinCount=1, MaxCount=1, InstanceType="t3.micro")[
        "Instances"
    ][0]["InstanceId"]
    terminate_run(_args("ec2", iid))
    captured = capsys.readouterr()
    assert "Terminated" in captured.out
    states = {
        i["InstanceId"]: i["State"]["Name"]
        for r in ec2.describe_instances()["Reservations"]
        for i in r["Instances"]
    }
    assert states[iid] in ("shutting-down", "terminated")


@mock_aws
def test_terminate_s3_refuses_nonempty(capsys):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="has-stuff")
    s3.put_object(Bucket="has-stuff", Key="file.txt", Body=b"hello")
    terminate_run(_args("s3", "has-stuff"))
    captured = capsys.readouterr()
    assert "Refusing" in captured.out
    # Bucket should still exist.
    assert "has-stuff" in [b["Name"] for b in s3.list_buckets()["Buckets"]]


@mock_aws
def test_terminate_s3_deletes_empty(capsys):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="empty-bucket")
    terminate_run(_args("s3", "empty-bucket"))
    captured = capsys.readouterr()
    assert "Deleted" in captured.out
    assert "empty-bucket" not in [b["Name"] for b in s3.list_buckets()["Buckets"]]


@mock_aws
def test_terminate_nonexistent_handles_clienterror(capsys):
    terminate_run(_args("ec2", "i-doesnotexist"))
    captured = capsys.readouterr()
    assert "AWS error" in captured.out
