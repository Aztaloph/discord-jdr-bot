# tests/unit/test_mj_permissions.py
"""Rôle Discord MJ — vérifications réutilisables."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from interfaces.discord.permissions.mj import (
    MJ_ROLE_NAME,
    build_mj_denied_embed,
    user_has_mj_role,
)


class TestMjPermissions(unittest.TestCase):
    def test_user_has_mj_role_true(self):
        member = MagicMock()
        role = MagicMock()
        role.name = MJ_ROLE_NAME
        member.roles = [role]
        self.assertTrue(user_has_mj_role(member))

    def test_user_has_mj_role_false(self):
        member = MagicMock()
        role = MagicMock()
        role.name = "Joueur"
        member.roles = [role]
        self.assertFalse(user_has_mj_role(member))

    def test_denied_embed_footer(self):
        embed = build_mj_denied_embed()
        self.assertIn("JDR Bot", embed.footer.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
