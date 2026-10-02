# Bot tests

```bash
./tests/run                  # the 40 that do not touch the machine
./tests/run --live           # plus the 8 diagnostic ones
./tests/run truncate_keeps_html_valid    # just one, with its full output
```

No dependencies: python3 and `git` (one of the tests builds real repos).

## How it works

`harness.py` brings up the **whole** bot against a fake Telegram and a fake
`HOME` in a temporary directory that is deleted on exit. Nothing they write
touches the `~/.config` of whoever runs them — not the muted-ports file, not
the saved menus of a running bot. The token is made up and the network layer
is replaced, so not one byte goes out to Telegram.

The bot is loaded with `SourceFileLoader` because the file does not end in
`.py`: `spec_from_file_location` returns `None` for a name it does not
recognise.

## The two groups

The **`live_*`** ones read the real state of this machine: systemd, Docker,
`ss`, the versions API. They are for seeing what is going on, not for
regression — their result depends on whether there is a paused session or
whether Docker has dangling images. That is why they do not run by default.

The rest are hermetic and should pass anywhere.

## They are checked by trying to break the bot

A suite that does not fail when you break something is useless, and the first
version of these tests did not fail. They are verified by reintroducing the
real bugs, one by one, and seeing which test catches each:

```bash
# with the bot broken by hand, ./run has to say "1 of 40 failed"
```

Of the ten historical bugs reintroduced, **all ten are caught**. The three
that slipped through at first taught more than the ones that were already
caught:

- The truncation poison cut between padding, not inside a tag. A text that is
  merely *long* gets cut just as well bare as with `truncate()`.
- Nobody tested `is_alive()`: every test replaces it with a lambda.
- The startup test **rewrote** the block instead of calling it, so it was
  checking a copy. That is why `handle_backlog()` came out of `main()`.

And two bad habits that let anything through: tests that **printed**
"expected 1" without asserting it, and tests that printed `==> FAILURES:` and
exited with code 0. The runner now looks at the exit code **and** the text.

An interesting case: removing the tap dedup broke nothing, because the
"already alive" check masks it. They are two defences for the same thing, so
that test now looks at how many times the tap *arrives*, not how many times it
takes effect.

## What each one covers, and which bug brought it

None was written for completeness: each one came out of something that broke.

| test | the bug that brought it |
|---|---|
| `menus_do_not_stack` | setup left two identical keyboards taking up the screen |
| `menus_from_previous_run` | a menu from before the restart kept its button greyed out forever |
| `pause_and_resume` | Resume never showed up: the tmux socket exists even if the server has died |
| `repeated_taps_in_one_batch` | three taps on Resume launched three services |
| `api_socket_timeout` | `_sock` travelled to Telegram as a parameter; 47 s of waiting per command |
| `late_commands_are_reported` | on startup, commands were dropped silently |
| `no_orphan_callbacks` | a new branch broke the `elif` chain and everything fell into "I don't know this button" |
| `truncate_keeps_html_valid` | `text[:4000]` split a `<code>` and Telegram dropped the message |
| `api_guards_every_send` | the truncation lived in `send()`, and two sends do not go through it |
| `callback_data_fits_in_64` | a long session name brought down sending the whole menu |
| `who_carries_the_menu` | `/help` hung the menu on itself and stole it from the message that had it |
| `questions_have_a_way_out` | `/close` asked "which one?" with no way to say "none" |
| `report_new_or_rewritten` | typing the command deleted the previous report |
| `codex_unit_states` | a unit that does not exist was painted as an outage |
| `hot_reload` | the bot kept running the old code after an install, three times |
| `ports_*`, `transient_ports_*`, `backup_*`, `send_*`, `session_close_*`, `text_commands_*`, `sends_that_bypass_*` | see the header of each file |
