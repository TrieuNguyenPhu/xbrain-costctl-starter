"""Pytest setup — make project root importable and seed AWS env vars."""
import os
import sys

# Make project root importable so tests can `from commands.list_cmd import ...`
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# moto needs SOME credentials present; these are dummy and never reach AWS.
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")
