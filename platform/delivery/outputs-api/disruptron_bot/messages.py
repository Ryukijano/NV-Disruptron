WELCOME = (
    "Welcome to <b>NV-Disruptron</b> — London transport intelligence.\n\n"
    "Send any message to chat with the agent (no slash commands needed).\n\n"
    "<b>Subscriptions</b>\n"
    "/subscribe_alerts — disruption push alerts\n"
    "/unsubscribe_alerts — stop alerts\n"
    "/subscribe_daily — morning daily plan digest\n"
    "/unsubscribe_daily — stop daily plan\n\n"
    "/help — show this menu again"
)

HELP = (
    "<b>NV-Disruptron Telegram</b>\n\n"
    "• <b>Direct chat</b> — type normally; your message is forwarded to the NV-Disruptron agent.\n"
    "• <b>Alerts</b> — /subscribe_alerts for heartbeat disruption notifications.\n"
    "• <b>Daily plan</b> — /subscribe_daily for the morning digest (backend-scheduled).\n\n"
    "Push delivery is orchestrated by the backend via the outputs-api gateway."
)

DENIED = "You are not authorized to use this bot."

SUBSCRIBED_ALERTS = (
    "You are subscribed to <b>disruption alerts</b>. "
    "You will receive text notifications when the backend detects material changes."
)

UNSUBSCRIBED_ALERTS = "Disruption alerts turned off."

SUBSCRIBED_DAILY = (
    "You are subscribed to the <b>daily plan</b> digest. "
    "The backend will push your morning briefing when ready."
)

UNSUBSCRIBED_DAILY = "Daily plan digest turned off."

THINKING = "Checking London transport data…"
