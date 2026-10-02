"""The watchdog does not alert about a server that lives as long as a test run.

From 21 September to 2 October there were 47 port alerts, 45 of them native
processes, and 28 from e2e-server.js, which grabs a different free port on
each run and dies when it ends: the 🔇 muted a port that was never used again.
"""
import subprocess, tempfile
import harness as H
WD = H.REPO / "bin/claude-rc-watchdog"

# The ports section is run on its own, from NET_ALLOW= to the end, with a fake
# ss, docker and clock. LISTEN is what listens on each round; DOCKER, the
# ports a container publishes.
def run(d, script):
    r = subprocess.run(["bash", "-c", f'''
set -u
STATE={d}; CLOCK=0; LISTEN=""; DOCKER=""
CLAUDE_RC_NET_ALLOW="tcp:22"; CLAUDE_RC_NET_ALLOW_FILE={d}/does-not-exist
# The clock starts far from 0: a marker that does not exist reads as 0, and
# with the clock at 0 it would look like an alert from one second ago.
date() {{ [ "$1" = "+%s" ] && echo $((CLOCK + 1000000)) || command date "$@"; }}
ss() {{ case "$*" in *-tuln*) for p in $LISTEN; do
          echo "tcp LISTEN 0 511 0.0.0.0:$p 0.0.0.0:*"; done ;; esac; }}
docker() {{ for p in $DOCKER; do printf 'db\\t0.0.0.0:%s->5432/tcp\\n' "$p"; done; }}
msg() {{ echo "$1"; }}; mute_button() {{ :; }}; log() {{ :; }}
ALERTS=""; tg() {{ ALERTS+="$1 "; }}
round() {{ eval "$(sed -n '/^NET_ALLOW=/,$p' {WD})"; }}
{script}
echo "$ALERTS"
'''], capture_output=True, text=True)
    assert not r.stderr, r.stderr
    return r.stdout.split()

with tempfile.TemporaryDirectory() as d:
    # An e2e run: a new port every 10 minutes, alive for 4 minutes.
    a = run(d, '''
for t in 0 1 2 3 4 5; do
  for m in 0 1 2 3 4 5 6 7 8 9; do
    CLOCK=$(( t*600 + m*60 )); LISTEN=""; [ $m -lt 4 ] && LISTEN="$((4600+t))"; round
  done
done''')
    print("  six 4-minute e2e runs:", len(a), "alerts")
    assert a == [], f"{a}: alerts about transient servers"

with tempfile.TemporaryDirectory() as d:
    # A server that stays: alerts once the grace runs out, and only once.
    a = run(d, '''
LISTEN="3000"
for ((CLOCK=0; CLOCK<=3600; CLOCK+=60)); do round; done''')
    print("  server up for an hour:", a)
    assert a == ["wd_net_native"], a

with tempfile.TemporaryDirectory() as d:
    # Docker bypasses ufw: that one alerts on the first round, no grace.
    a = run(d, 'LISTEN="5432"; DOCKER="5432"; round')
    print("  published by Docker, first round:", a)
    assert a == ["wd_net_docker"], a

with tempfile.TemporaryDirectory() as d:
    # The grace is CONTINUOUS: if the port goes away halfway, the clock resets.
    a = run(d, '''
LISTEN="8080"
for ((CLOCK=0; CLOCK<=600; CLOCK+=60)); do round; done
LISTEN=""; CLOCK=660; round
LISTEN="8080"
for ((CLOCK=720; CLOCK<=1200; CLOCK+=60)); do round; done
ls $STATE''')
    print("  10 min, drops, 8 min:", a)
    assert "wd_net_native" not in a, "the grace does not reset when the port goes away"
print("\n==> OK")
