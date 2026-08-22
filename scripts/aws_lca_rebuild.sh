#!/usr/bin/env bash
#
# Rebuild data/h1b/lca_by_university.json on EC2 instead of locally.
#
# WHY THIS EXISTS
#   The LCA aggregation needs a ~6 GB csv_cache derived from ~3.6 GB of XLSX.
#   That does not fit on a full local disk. Everything else in the pipeline is
#   small enough to run locally; this is the one job that is not.
#
# WHAT IT DOES NOT DO
#   It does not reimplement the aggregation. It ships pipeline/state.py,
#   pipeline/step3_parse_federal.py and pipeline/entity_map.json to the
#   instance and calls _parse_lca_files() there, so the result is identical to
#   a local run. The only thing done differently is that the XLSX -> CSV
#   transcription runs across cores; that is a pure format conversion and the
#   pipeline skips any CSV already present, so it cannot change the output.
#
# USAGE
#   export AWS_PROFILE=personal
#   scripts/aws_lca_rebuild.sh            # launch and poll
#   scripts/aws_lca_rebuild.sh --fetch    # just download a finished result
#
# COST
#   c7i.4xlarge on demand, roughly half an hour: well under a dollar. The
#   instance terminates itself on completion, on failure, and on any crash
#   (instance-initiated-shutdown-behavior=terminate plus an EXIT trap).
set -euo pipefail

BUCKET=s3://phd-demographics-raw-data
PREFIX=$BUCKET/jobs/lca-rebuild
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=$REPO/data/h1b/lca_by_university.json
LEGAL_OUT=$REPO/data/h1b/lca_legal_by_university.json

# Resources verified present in account 534145494912 / us-east-1.
INSTANCE_TYPE=c7i.4xlarge
SUBNET=subnet-e5d961ce                       # vpc-bc3415d9, routes to igw-4999fd2c
PROFILE_NAME=EC2-S3-Migration-Profile        # AmazonS3FullAccess + SSM core
SG_NAME=lca-rebuild-egress
VOLUME_GB=100                                # xlsx + csv_cache + duckdb spill

die() { echo "ERROR: $*" >&2; exit 1; }

# Sanity checks live in heredocs rather than inline `python3 -c`: quoting a
# python one-liner inside a bash function is how the previous revision of this
# file ended up with a syntax error that only surfaced after a 20-minute job.
_check_totals() {
    python3 - "$1" <<'PYCHK'
import json, sys
d = json.load(open(sys.argv[1]))
assert len(d) > 50, f"only {len(d)} universities"
print(f"  {len(d)} universities, {sum(v['total_lcas'] for v in d.values()):,} LCAs")
PYCHK
}

_check_legal() {
    python3 - "$1" <<'PYCHK'
import json, sys
d = json.load(open(sys.argv[1]))
m = d["_meta"]
assert d["firms"] or d["attorneys"], "no firms and no attorneys"
print(f"  {m['distinct_firms']:,} firms, {m['distinct_attorneys']:,} attorneys, "
      f"{m['attorneys_with_an_email']:,} with an email")
PYCHK
}

fetch_one() {         # $1 remote name, $2 destination, $3 checker function
    local tmp want got; tmp=$(mktemp)
    aws s3 cp "$PREFIX/$1" "$tmp" --only-show-errors || die "no $1 on S3 yet"
    # Prove we got the bytes the job produced before touching the real file.
    want=$(aws s3 cp "$PREFIX/$1.sha256" - 2>/dev/null | awk '{print $1}')
    got=$(shasum -a 256 "$tmp" | awk '{print $1}')
    if [ -n "$want" ] && [ "$want" != "$got" ]; then die "checksum mismatch on $1"; fi
    "$3" "$tmp" || die "$1 failed its sanity check; left $2 untouched"
    mv "$tmp" "$2"
    echo "  wrote $2"
}

fetch() {
    fetch_one lca_by_university.json       "$OUT"       _check_totals
    fetch_one lca_legal_by_university.json "$LEGAL_OUT" _check_legal
}

if [ "${1:-}" = "--fetch" ]; then fetch; exit 0; fi

command -v aws >/dev/null || die "aws cli not found"
aws sts get-caller-identity >/dev/null 2>&1 || die "no AWS credentials (set AWS_PROFILE)"

echo "==> packaging job"
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/pipeline"
cp "$REPO"/pipeline/{__init__.py,state.py,step3_parse_federal.py,entity_map.json} "$WORK/pipeline/"
cp "$REPO"/scripts/aws_lca/run_lca.py "$WORK/"
cp "$REPO"/requirements.lock "$WORK/"      # the box installs what this pins
tar -C "$WORK" -czf "$WORK/job.tar.gz" pipeline run_lca.py requirements.lock
aws s3 cp "$WORK/job.tar.gz" "$PREFIX/job.tar.gz" --only-show-errors
echo "STAGED" | aws s3 cp - "$PREFIX/status.txt" --only-show-errors

echo "==> resolving image and security group"
AMI=$(aws ssm get-parameter \
    --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
    --query 'Parameter.Value' --output text)
VPC=$(aws ec2 describe-subnets --subnet-ids "$SUBNET" --query 'Subnets[0].VpcId' --output text)
SG=$(aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC" \
        --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
if [ -z "$SG" ] || [ "$SG" = "None" ]; then
    SG=$(aws ec2 create-security-group --group-name "$SG_NAME" \
            --description "LCA rebuild: egress only, no inbound" \
            --vpc-id "$VPC" --query 'GroupId' --output text)
fi
echo "    ami=$AMI sg=$SG (no inbound; SSM works over egress)"

echo "==> launching"
IID=$(aws ec2 run-instances \
    --image-id "$AMI" --instance-type "$INSTANCE_TYPE" \
    --subnet-id "$SUBNET" --security-group-ids "$SG" \
    --iam-instance-profile "Name=$PROFILE_NAME" --associate-public-ip-address \
    --block-device-mappings "[{\"DeviceName\":\"/dev/xvda\",\"Ebs\":{\"VolumeSize\":$VOLUME_GB,\"VolumeType\":\"gp3\",\"DeleteOnTermination\":true}}]" \
    --instance-initiated-shutdown-behavior terminate \
    --user-data "file://$REPO/scripts/aws_lca/bootstrap.sh" \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=lca-rebuild},{Key=Project,Value=phd-demographics}]' \
    --query 'Instances[0].InstanceId' --output text)
echo "    $IID"

echo "==> polling (ctrl-c is safe; the instance still terminates itself)"
prev=""
while :; do
    cur=$(aws s3 cp "$PREFIX/status.txt" - 2>/dev/null | tr -d '\n' || true)
    [ "$cur" != "$prev" ] && [ -n "$cur" ] && { echo "    $cur"; prev=$cur; }
    case "$cur" in
        DONE) break;;
        FAILED*) aws s3 cp "$PREFIX/run.log" - 2>/dev/null | tail -40; die "job failed: $cur";;
    esac
    sleep 20
done

echo "==> fetching result"
fetch
