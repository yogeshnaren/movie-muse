"""No-training defaults, erasure, export, and residency."""

from __future__ import annotations

from collections.abc import Callable

import pytest
import yaml

from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Principal, Role
from movie_muse.privacy.api import (
    CROSS_USER_PROMPT_CACHE,
    NO_TRAINING_DEFAULT,
    ErasedError,
    PrivacyError,
    RetentionError,
    TrainingConsentError,
)
from movie_muse.security.api import ControlPlane
from movie_muse.toolchain.paths import repo_root


def test_no_training_default_matches_consent_policy() -> None:
    payload = yaml.safe_load(
        (repo_root() / "policy" / "models" / "consent.yaml").read_text(encoding="utf-8")
    )
    consent = dict(payload["consent"])
    assert consent["no_training_default"] is True
    assert consent["cross_user_prompt_cache"] is False
    assert NO_TRAINING_DEFAULT is True
    assert CROSS_USER_PROMPT_CACHE is False


def test_training_stays_off_until_acl_opt_in(
    plane: ControlPlane, member: Callable[[Role], Principal]
) -> None:
    policy = plane.privacy.training_policy()
    assert policy.no_training_default is True
    assert policy.opt_in is False
    with pytest.raises(TrainingConsentError):
        plane.privacy.assert_training_allowed()
    plane.privacy.assert_no_cross_user_cache()
    writer = member(Role.WRITER)
    with pytest.raises(AuthorizationError):
        plane.privacy.grant_training_opt_in(principal=writer, acl_epoch=plane.epoch)
    granted = plane.privacy.grant_training_opt_in(principal=plane.principal, acl_epoch=plane.epoch)
    assert granted.opt_in is True
    plane.privacy.assert_training_allowed()


def test_erase_then_export_fail_closed(
    plane: ControlPlane, member: Callable[[Role], Principal]
) -> None:
    subject = "actor_erased"
    record = plane.privacy.erase_subject(
        subject, principal=plane.principal, acl_epoch=plane.epoch, retain_days=30
    )
    assert record.id.startswith("prv_")
    with pytest.raises(ErasedError):
        plane.privacy.assert_readable(subject)
    with pytest.raises(RetentionError):
        plane.privacy.assert_readable(subject, now="2099-01-01T00:00:00Z")
    with pytest.raises(PrivacyError):
        plane.privacy.export_subject(
            plane.principal.actor_id,
            principal=plane.principal,
            acl_epoch=plane.epoch,
            payload={"token": "should-not-export"},
        )
    exported = plane.privacy.export_subject(
        plane.principal.actor_id,
        principal=plane.principal,
        acl_epoch=plane.epoch,
        payload={"display_name": "Owner"},
    )
    assert exported.training_opt_in is False
    viewer = member(Role.VIEWER)
    with pytest.raises(AuthorizationError):
        plane.privacy.export_subject(
            plane.principal.actor_id,
            principal=viewer,
            acl_epoch=plane.epoch,
            payload={"display_name": "Owner"},
        )


def test_residency_private_route(plane: ControlPlane) -> None:
    value = plane.privacy.set_residency("private_route", principal=plane.principal, acl_epoch=plane.epoch)
    assert value == "private_route"


@pytest.mark.architecture
def test_privacy_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "privacy"
    siblings = ("audit", "authorization", "identity", "persistence", "schemas", "security")
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for sibling in siblings:
            private_prefix = f"from movie_muse.{sibling}."
            public_import = f"from movie_muse.{sibling}.api import"
            assert private_prefix not in text.replace(public_import, "")
        assert "from tests." not in text
