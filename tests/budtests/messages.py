"""Texts and names the Bud suites expect the UI to show."""


class UiCliAuth:
    """Texts and names of the ui_cli_auth suite."""

    BOX_NAME = "Request code character {number} of {boxes}"
    GROUP_NAME = "Request code"
    HELP = "Type the code your terminal or AI client shows next to the link."
    UNVERIFIED = "Client name, as given by the requesting client (not verified)"
    ACCOUNT = "Approving signs this client in to Bud as {name} ({email}), with your full permissions."
    TIMES = "Requested {requested}. Expires {expires}."
    WARNING = "Approve only a sign-in you started yourself, on your own computer, in the last few minutes."
    CODE_WARNING = "Code sign-in: after you approve, this page shows a one-time code. Anyone who has that code can sign in to Bud as you until it expires."
    APPROVE = "Approve"
    DENY = "Deny"
    CANCEL = "Cancel"
    COPY = "Copy code"
    PASTE_ONLY = "Paste this code only into the client where you started this sign-in. Never send it to anyone."
    MATCH = "The code matches."
    MISMATCH = "This code does not match. Check the code in your terminal, or deny this request."
    LIMITED = "Too many attempts. Wait a minute and try again."
    ENDED = "This authorization session has expired or has already been used."
    DENIED = "Sign-in request denied. This link no longer works. You can close this page."
