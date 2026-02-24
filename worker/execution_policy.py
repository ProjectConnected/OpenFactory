from __future__ import annotations

from dataclasses import dataclass


SHELL_METACHARS = set("|&;><`$")
BANNED_BINARIES = {"curl", "wget", "rm", "dd", "mkfs", "shutdown", "reboot", "poweroff"}


@dataclass(frozen=True)
class CommandPolicy:
    allowed: set[tuple[str, str]]

    def validate(self, argv: list[str]) -> None:
        if len(argv) < 2:
            raise RuntimeError("deny_by_default_command_blocked")

        bin_name = argv[0].strip()
        if bin_name in BANNED_BINARIES:
            raise RuntimeError(f"command_blocked_banned_binary={bin_name}")

        if (argv[0], argv[1]) not in self.allowed:
            raise RuntimeError(f"deny_by_default_command_blocked cmd={argv}")

        for token in argv:
            if any(ch in SHELL_METACHARS for ch in token):
                raise RuntimeError(f"command_blocked_shell_metachar token={token}")

        if argv[0] == "git" and argv[1] == "push":
            joined = " ".join(argv)
            if " origin main" in f" {joined}" or " origin master" in f" {joined}":
                raise RuntimeError("blocked_push_to_protected_branch")
