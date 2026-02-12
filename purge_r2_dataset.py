"""
Purge objects under R2 dataset prefix.

Usage:
  python purge_r2_dataset.py --yes
  python purge_r2_dataset.py --prefix market_data --yes
"""

from __future__ import annotations

import argparse
import os

import boto3
from dotenv import load_dotenv


def env_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Purge R2 dataset prefix")
    p.add_argument("--prefix", default=os.getenv("R2_DATASET_PREFIX", "market_data"))
    p.add_argument("--yes", action="store_true", help="required to execute delete")
    return p.parse_args()


def main() -> None:
    load_dotenv(".env.r2.local", override=False)
    load_dotenv(".env.local", override=False)
    load_dotenv(".env", override=False)

    args = parse_args()
    if not args.yes:
        raise RuntimeError("--yes flag is required for destructive purge")

    endpoint = env_required("R2_ENDPOINT")
    bucket = env_required("R2_BUCKET")
    key = env_required("R2_ACCESS_KEY_ID")
    secret = env_required("R2_SECRET_ACCESS_KEY")
    region = os.getenv("R2_REGION", "auto")
    prefix = args.prefix.strip("/").rstrip("/") + "/"

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        region_name=region,
    )

    total = 0
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        objs = [{"Key": x["Key"]} for x in resp.get("Contents", [])]
        if objs:
            for i in range(0, len(objs), 1000):
                chunk = objs[i : i + 1000]
                s3.delete_objects(Bucket=bucket, Delete={"Objects": chunk, "Quiet": True})
                total += len(chunk)
                print(f"deleted={total}")
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")

    print(f"PURGE_DONE bucket={bucket} prefix={prefix} deleted={total}")


if __name__ == "__main__":
    main()

