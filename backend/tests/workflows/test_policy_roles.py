"""Policy role resolution tests."""
from app.workflows.policy import PolicyResolutionError, get_user_role


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return _FakeResult(self._data)


class _FakeClient:
    def __init__(self, role: str | None):
        self._role = role

    def table(self, name: str):
        assert name == "organization_members"
        if self._role is None:
            return _FakeQuery([])
        return _FakeQuery([{"role": self._role}])


def test_get_user_role_accepts_owner():
    client = _FakeClient("owner")
    assert get_user_role(client, "org-1", "user-1") == "owner"


def test_get_user_role_accepts_admin():
    client = _FakeClient("admin")
    assert get_user_role(client, "org-1", "user-1") == "admin"


def test_get_user_role_rejects_unknown_role():
    client = _FakeClient("viewer")
    try:
        get_user_role(client, "org-1", "user-1")
        assert False, "expected PolicyResolutionError"
    except PolicyResolutionError as exc:
        assert "viewer" in str(exc)
