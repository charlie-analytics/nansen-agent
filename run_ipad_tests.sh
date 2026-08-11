#!/usr/bin/env bash
# Runs every test suite for the iPad tools and records the output.
#
#     ./run_ipad_tests.sh            # run and print
#     ./run_ipad_tests.sh --record   # also overwrite TEST-RUNS.md
#
# Exits non-zero if any suite fails.

set -uo pipefail
cd "$(dirname "$0")"

RECORD=0
[ "${1:-}" = "--record" ] && RECORD=1

OUT=$(mktemp)
STATUS=0

{
  echo "Recorded: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "Python:   $(python3 --version 2>&1)"
  echo "Node:     $(node --version 2>&1)"
  echo "Pillow:   $(python3 -c 'import PIL; print(PIL.__version__)' 2>&1)"
  echo "Platform: $(uname -sr)"
  echo
  echo "########################################"
  echo "# Suite 1: photo dedupe (Python)"
  echo "########################################"
  echo
} >>"$OUT"

python3 photo-dedupe/test_dedupe.py >>"$OUT" 2>&1 || STATUS=1

{
  echo
  echo "########################################"
  echo "# Suite 2: job watcher (JavaScript)"
  echo "########################################"
  echo
} >>"$OUT"

( cd ipad-agents && node test_job_watcher.mjs ) >>"$OUT" 2>&1 || STATUS=1

if [ "$STATUS" -eq 0 ]; then
  echo >>"$OUT"
  echo "ALL SUITES PASSED" >>"$OUT"
else
  echo >>"$OUT"
  echo "SOME SUITES FAILED" >>"$OUT"
fi

cat "$OUT"

if [ "$RECORD" -eq 1 ]; then
  {
    echo '# Recorded test runs'
    echo
    echo 'Output of `./run_ipad_tests.sh`, committed so the results can be read'
    echo 'without running anything. Regenerate with `./run_ipad_tests.sh --record`.'
    echo
    echo '**These run on Linux, not on an iPad.** They cover the matching logic and'
    echo 'the adapters around it, using mocks in place of PhotoKit and Scriptable.'
    echo 'Nothing here proves behaviour on a physical device — see the'
    echo '"What is not covered" section at the bottom.'
    echo
    echo '```'
    cat "$OUT"
    echo '```'
    echo
    cat TEST-RUNS-FOOTER.md 2>/dev/null
  } >TEST-RUNS.md
  echo
  echo "Recorded to TEST-RUNS.md"
fi

rm -f "$OUT"
exit "$STATUS"
