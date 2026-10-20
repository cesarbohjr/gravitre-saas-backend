from app.services.msp_org_context import msp_parent_grants_access


class _Table:
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


class _Client:
    def __init__(self, parent: str | None):
        self._parent = parent

    def table(self, name: str):
        assert name == "organizations"
        return _Table(self._parent)


def test_parent_membership_alone_does_not_grant_client_access():
    client = _Client("parent-org")
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
