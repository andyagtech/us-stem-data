#!/bin/bash
# Runs on the EC2 instance via user-data. Streams a log to S3 throughout so
# progress is visible without SSH, and always uploads the log even on failure.
exec > /var/log/lca-rebuild.log 2>&1
set -x

S3=s3://phd-demographics-raw-data
PREFIX=$S3/jobs/lca-rebuild
WORK=/mnt/work

push_log() { aws s3 cp /var/log/lca-rebuild.log $PREFIX/run.log --only-show-errors || true; }
status()   { echo "$1" | aws s3 cp - $PREFIX/status.txt --only-show-errors || true; push_log; }
# Whatever happens -- success, crash, or spot reclaim -- the log lands in S3.
trap 'rc=$?; push_log; echo "exit=$rc"; [ $rc -ne 0 ] && status "FAILED rc=$rc"; shutdown -h +2' EXIT

status "STARTING"

# The root volume is small; the 6GB csv_cache goes on the big EBS volume.
mkdir -p $WORK && cd $WORK

dnf install -y python3.11 python3.11-pip >/dev/null

status "FETCHING_CODE"
aws s3 cp $PREFIX/job.tar.gz . --only-show-errors
tar xzf job.tar.gz

# Install the versions requirements.lock pins, never hardcoded ones. An
# earlier revision of this script pinned duckdb==1.1.3 while the lockfile
# said 1.5.5; the job then failed on a binder rule that differs between
# them, after the local test suite had passed on 1.5.5. The whole point of
# the lockfile is that the box and the laptop run the same code.
DUCKDB=$(grep -iE '^duckdb==' requirements.lock)
OPENPYXL=$(grep -iE '^openpyxl==' requirements.lock)
[ -n "$DUCKDB" ] && [ -n "$OPENPYXL" ] || { echo "lockfile missing duckdb/openpyxl"; exit 1; }
echo "installing $DUCKDB $OPENPYXL"
python3.11 -m pip install --quiet "$DUCKDB" "$OPENPYXL"

status "FETCHING_XLSX"
mkdir -p data/h1b/lca
aws s3 sync $S3/data/h1b/lca/ data/h1b/lca/ --exclude "*" --include "*.xlsx" --only-show-errors
ls -la data/h1b/lca/ | head -40
df -h $WORK

status "RUNNING"
python3.11 run_lca.py; rc=$?
push_log

if [ $rc -ne 0 ]; then status "FAILED_JOB rc=$rc"; exit $rc; fi

status "UPLOADING"
aws s3 cp lca_by_university.json $PREFIX/lca_by_university.json --only-show-errors
# A checksum lets the local side prove it got the bytes the job produced.
sha256sum lca_by_university.json | tee /tmp/sum.txt
aws s3 cp /tmp/sum.txt $PREFIX/lca_by_university.json.sha256 --only-show-errors

status "DONE"
