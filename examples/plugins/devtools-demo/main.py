"""One plugin entry; sibling modules use package-relative imports."""

from .actions import action
from .views import render


def register(host):
    host.register_command("ui.render", render)
    host.register_command("ui.action", action)
