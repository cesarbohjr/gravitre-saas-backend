from app.services.msp_org_context import msp_parent_grants_access


class _OrgTable:
    """Fake organizations table that returns parent_org_id."""

    def __init__(self, parent: str | None):
        self._parent = parent

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        class R:
            data = [{"parent_org_id": self._parent}]

        return R()


class _MemberTable:
    """Fake organization_members table that returns a given role."""

    def __init__(self, role: str | None):
        self._role = role

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        class R:
            data = [{"role": self._role}] if self._role else []

        return R()


class _Client:
    """Fake Supabase client.

    ``parent``: the parent_org_id the organizations table reports for any child.
    ``admin_role``: the role the organization_members table reports for any user.
    """

    def __init__(self, parent: str | None, admin_role: str | None = "admin"):
        self._parent = parent
        self._admin_role = admin_role

    def table(self, name: str):
        if name == "organizations":
            return _OrgTable(self._parent)
        if name == "organization_members":
            return _MemberTable(self._admin_role)
        raise AssertionError(f"Unexpected table: {name}")


def test_parent_membership_alone_does_not_grant_client_access():
    """Member role (not admin) in parent org — access denied."""
    client = _Client("parent-org", admin_role="member")
    assert not msp_parent_grants_access(
        client,
        user_id="u1",
        requested_org_id="child-org",
        member_org_ids=["parent-org"],
    )


def test_sibling_member_denied():
    client = _Client("parent-org")
    assert not msp_parent_grants_access(
        client,
        user_id="u1",
        requested_org_id="child-b",
        member_org_ids=["child-a"],
    )


def test_explicit_client_and_parent_memberships_recognize_relationship():
    assert msp_parent_grants_access(_Client("parent-org"), user_id="u1", requested_org_id="child-org", member_org_ids=["parent-org", "child-org"])
