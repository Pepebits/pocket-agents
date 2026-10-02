"""The watchdog's down alert: with a button, backing off, and per session.

The QueueEngine outage of 18 September -21.5 h- was 21 identical alerts
saying "Tap 🔑" without the button being in the message.
"""
import subprocess, tempfile, pathlib
import harness as H
WD = H.REPO / "bin/claude-rc-watchdog"
with tempfile.TemporaryDirectory() as d:
    r = subprocess.run(["bash", "-c", f'''
STATE={d}; CLOCK=0; unset s
date() {{ [ "$1" = "+%s" ] && echo "$CLOCK" || command date "$@"; }}
msg() {{ echo "$1"; }}; login_button() {{ echo "BUTTON:$1"; }}
N=0; B=0; tg() {{ N=$((N+1)); [ "${{2:-}}" = "BUTTON:QueueEngine" ] && B=$((B+1)); }}
eval "$(sed -n "/^alert_down()/,/^}}/p" {WD})"
for ((CLOCK=0; CLOCK<=77400; CLOCK+=70)); do alert_down QueueEngine x; done
echo "$N $B"
CLOCK=0; N=0; rm -f {d}/*; alert_down CalEngine x; alert_down travel x
echo "$N $(ls {d} | tr '\\n' ' ')"
'''], capture_output=True, text=True)
    lines = r.stdout.split("\n")
    n, b = map(int, lines[0].split())
    print(f"  21.5 h outage: {n} alerts, {b} with ITS session's button   stderr={r.stderr!r}")
    assert 3 <= n <= 6, f"{n} alerts: the back-off does not work (it used to be 21)"
    assert b == n, "some alert without a button, or with another session's"
    assert not r.stderr, "it litters the journal"
    print("  two sessions:", lines[1])
    assert "CalEngine.alert-down" in lines[1] and "travel.alert-down" in lines[1], \
        "they share a marker: the 'local' expands $s before assigning it"
print("\n==> OK")
