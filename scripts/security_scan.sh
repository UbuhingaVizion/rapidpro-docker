#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Vulnerability scan + SBOM for every image this stack runs.
#
#   ./scripts/security_scan.sh                  # scan the digest-pinned images
#   ./scripts/security_scan.sh --include-built  # ... plus the locally built ones
#   ./scripts/security_scan.sh --sbom           # also emit CycloneDX SBOMs
#   ./scripts/security_scan.sh --include-built --sbom
#
# Images are read straight out of docker-compose.yml, so bumping a pin is enough
# for it to be scanned; the Dockerfile build stages are covered transitively by
# their output.
#
# Exits non-zero if any CRITICAL vulnerability *with a published fix* is present
# and not accepted in .trivyignore.yaml. HIGH/MEDIUM/LOW are reported (SARIF +
# summary) but do not fail the run: most of them live in packages this repo
# cannot pin (fork lockfiles, EOL Elasticsearch 7.17, Debian LTS). See the
# README "Security" section for the policy.
#
# Requires: docker, trivy (>= 0.60 for .trivyignore.yaml) + python3.
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_ROOT/docker-compose.yml}"
IGNORE_FILE="${IGNORE_FILE:-$REPO_ROOT/.trivyignore.yaml}"
OUT_DIR="${OUT_DIR:-$REPO_ROOT/.security}"
TRIVY="${TRIVY:-trivy}"
TRIVY_VERSION="${TRIVY_VERSION:-0.76.1}"

INCLUDE_BUILT=0
MAKE_SBOM=0
for arg in "$@"; do
    case "$arg" in
        --include-built) INCLUDE_BUILT=1 ;;
        --sbom) MAKE_SBOM=1 ;;
        -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown argument: $arg" >&2; exit 2 ;;
    esac
done

if ! command -v "$TRIVY" >/dev/null 2>&1; then
    echo "trivy not found. Install it (CI pins v${TRIVY_VERSION}) or set TRIVY=/path/to/trivy:" >&2
    echo "  curl -sSL https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz | tar -xz -C /usr/local/bin trivy" >&2
    exit 1
fi

mkdir -p "$OUT_DIR"
SUMMARY="$OUT_DIR/summary.txt"
: > "$SUMMARY"

slugify() { printf '%s' "$1" | sed 's|@sha256:.*||; s|[/:]|_|g'; }

# --- collect the image set (all compose images are digest-pinned) ----------
mapfile -t REFS < <(
    grep -E '^[[:space:]]+image:[[:space:]]' "$COMPOSE_FILE" \
        | sed -E 's/^[[:space:]]*image:[[:space:]]*//; s/[[:space:]]+#.*$//; s/^"//; s/"$//' \
        | sort -u
)
if [ "$INCLUDE_BUILT" = 1 ]; then
    REFS+=(
        rapidpro-rapidpro:latest rapidpro-mailroom:latest rapidpro-courier:latest
        rapidpro-indexer:latest rapidpro-archiver:latest
    )
fi

count() { # count <file> <severity>
    python3 - "$1" "$2" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print(0); raise SystemExit
print(sum(1 for r in d.get("Results") or []
          for v in r.get("Vulnerabilities") or []
          if v.get("Severity") == sys.argv[2]))
PY
}

printf 'scanning %d image(s); gate = CRITICAL with a published fix; accepted set = %s\n\n' \
    "${#REFS[@]}" "${IGNORE_FILE#"$REPO_ROOT"/}"
printf '%-46s %5s %5s %5s %5s  %s\n' IMAGE CRIT HIGH MED LOW GATE | tee -a "$SUMMARY"

gate_failed=0
for ref in "${REFS[@]}"; do
    slug="$(slugify "$ref")"
    full="$OUT_DIR/$slug.json"

    # 1) report pass: all severities, unfixed included -> SARIF + counts
    if ! "$TRIVY" image --quiet --no-progress --scanners vuln \
            --ignorefile "$IGNORE_FILE" \
            --format json --output "$full" "$ref"; then
        echo "scan failed for $ref" >&2; exit 2
    fi
    "$TRIVY" convert --quiet --format sarif --output "$OUT_DIR/$slug.sarif" "$full" 2>/dev/null || true

    # 2) gate pass: CRITICAL that has a fix, minus the accepted set
    set +e
    "$TRIVY" image --quiet --no-progress --scanners vuln \
        --severity CRITICAL --ignore-unfixed --ignorefile "$IGNORE_FILE" \
        --exit-code 1 --format json --output "$OUT_DIR/$slug.crit.json" "$ref" >/dev/null 2>&1
    rc=$?
    set -e
    [ "$rc" -ge 2 ] && { echo "scan failed for $ref" >&2; exit "$rc"; }

    # 3) optional SBOM (all components, not just the vulnerable ones)
    if [ "$MAKE_SBOM" = 1 ]; then
        "$TRIVY" image --quiet --no-progress --scanners vuln \
            --format cyclonedx --output "$OUT_DIR/$slug.cdx.json" "$ref" >/dev/null 2>&1 || true
    fi

    if [ "$rc" -eq 1 ]; then gate="FAIL"; gate_failed=1; else gate="ok"; fi
    printf '%-46s %5s %5s %5s %5s  %s\n' "${ref%@sha256:*}" \
        "$(count "$full" CRITICAL)" "$(count "$full" HIGH)" \
        "$(count "$full" MEDIUM)" "$(count "$full" LOW)" "$gate" | tee -a "$SUMMARY"
done

echo
# Merge the per-image SARIF into one file (SARIF allows multiple `runs`) so the
# workflow can upload a single report to code scanning.
python3 - "$OUT_DIR" <<'PY' || true
import glob, json, os, sys
out = sys.argv[1]
runs, version = [], "2.1.0"
for f in sorted(glob.glob(os.path.join(out, "*.sarif"))):
    try:
        d = json.load(open(f))
    except Exception:
        continue
    version = d.get("version", version)
    for i, r in enumerate(d.get("runs", [])):
        r.setdefault("automationDetails", {})["id"] = os.path.basename(f) + f"#{i}"
        runs.append(r)
if runs:
    json.dump({"version": version, "runs": runs},
              open(os.path.join(out, "combined.sarif"), "w"), indent=1)
PY

if [ "$gate_failed" -ne 0 ]; then
    echo "FAILED: unaccepted CRITICAL vulnerabilities (see $OUT_DIR/*.crit.json)." >&2
    echo "Fix by moving the pin, or add a justified, expiring entry to .trivyignore.yaml." >&2
    exit 1
fi
echo "OK: no unaccepted CRITICAL vulnerabilities. Reports in $OUT_DIR/"

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
        echo "### Container vulnerability scan"
        echo '```'
        cat "$SUMMARY"
        echo '```'
        echo "Gate: **CRITICAL with a published fix**. Accepted exceptions live in \`.trivyignore.yaml\`."
    } >> "$GITHUB_STEP_SUMMARY"
fi
