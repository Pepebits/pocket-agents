"""handle(): a tap on a button has to be answered (answerCallbackQuery)
BEFORE the network request that adopt_menu() fires to strip the buttons off
ANOTHER menu -otherwise the button keeps spinning until api()'s _sock (45 s
by default), and if that request blows up, there is no ack at all.

The real scenario: a tap arrives on a menu the bot does not have registered
in MENUS (one from a previous run, see menus_from_previous_run).
adopt_menu() moves tracking to that message and strip_buttons() the one that
was there before -that is an editMessageReplyMarkup, real network- before
the bot answers the tap.
"""
import harness as H
bot = H.bot
bot.sessions = lambda: []
bot.MENUS.clear()
bot.MENUS[50] = ""          # the "old" menu, which adopt_menu() is going to strip

H.LOG.clear()
u = {
    "update_id": 1,
    "callback_query": {
        "id": "cq1",
        "from": {"id": bot.CHAT},
        "data": "status",
        "message": {
            "message_id": 99,           # ANOTHER message: not in MENUS
            "reply_markup": {"inline_keyboard": [[
                {"text": "Status", "callback_data": "status"}]]},
        },
    },
}
bot.handle(u)

print("order of API calls:", H.LOG)
assert "answerCallbackQuery" in H.LOG, "the tap was never answered"
assert "editMessageReplyMarkup" in H.LOG, "the test did not exercise adopt_menu()/strip_buttons()"
i_ack = H.LOG.index("answerCallbackQuery")
i_strip = H.LOG.index("editMessageReplyMarkup")
assert i_ack < i_strip, (
    f"the ack (pos {i_ack}) has to go BEFORE stripping the other menu "
    f"(pos {i_strip}), not after"
)

print("\n==> OK")
