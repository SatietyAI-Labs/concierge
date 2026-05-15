"""Tests for core.lifecycle_store.escalation — Stage 1A item 5.

Three exhaustively-pinned sets + four predicate/validator/inferrer
functions. These tests guard the routing-vocabulary surface so a
future addition (new escalation target, new worker codename) trips
exactly one test class with a clear forward-update path.

Coverage:

- ESCALATION_TARGET_VALUES exhaustively {"alfred", "operator"}
- WORKER_AGENT_IDS exhaustively {"scout", "dispatch", "radar", "bridge"}
  (alfred deliberately excluded — alfred-as-filer isn't worker form)
- is_worker_form predicate across the four trigger paths
- WorkerFormError surfaces all missing fields in one shot
- infer_escalation_target: worker→alfred / alfred→None / unknown→None /
  case-insensitive lookup
- worker_filename_prefix: worker→"worker-<name>" / non-worker→None /
  None→None
- Category-agnostic skill-context fixture exercises the worker-form
  predicates on a skill request (proves the routing surface is
  category-neutral per items-5+6 scope clarification).
"""
from __future__ import annotations

import pytest

from core.lifecycle_store.escalation import (
    ESCALATION_TARGET_VALUES,
    WORKER_AGENT_IDS,
    WorkerFormError,
    infer_escalation_target,
    is_worker_form,
    validate_worker_form,
    worker_filename_prefix,
)


# ---- Set exhaustiveness ----------------------------------------------------


class TestEscalationTargetValues:
    """Pinning the routing-target vocabulary. A future addition (e.g.
    "discord") must extend this set, the API endpoint's Literal, the
    docstring on Request.escalation_target, and this assertion in
    lock-step — D24 exhaustiveness pattern.
    """

    def test_contains_exactly_alfred_and_operator(self):
        assert ESCALATION_TARGET_VALUES == frozenset({"alfred", "operator"})

    def test_is_frozenset(self):
        """Hashability + immutability prevent accidental in-place
        mutation across imports.
        """
        assert isinstance(ESCALATION_TARGET_VALUES, frozenset)


class TestWorkerAgentIds:
    """Pinning the four-worker set. Alfred is intentionally excluded:
    Alfred-as-filer doesn't escalate to himself, and worker-form
    semantics (auto-infer alfred as escalation_target, prefix filename
    with `worker-`) don't apply.
    """

    def test_contains_exactly_four_workers(self):
        assert WORKER_AGENT_IDS == frozenset(
            {"scout", "dispatch", "radar", "bridge"}
        )

    def test_excludes_alfred(self):
        """Alfred-as-filer is allowed by the CLI's _ACCEPTED_AGENT_IDS
        but is NOT a worker. This test pins the distinction.
        """
        assert "alfred" not in WORKER_AGENT_IDS


# ---- is_worker_form predicate ----------------------------------------------


class TestIsWorkerForm:
    def test_pure_alfred_form_returns_false(self):
        assert not is_worker_form(
            agent_id=None,
            escalation_target=None,
            gap=None,
            workaround_used=None,
        )

    def test_alfred_as_agent_id_alone_is_not_worker_form(self):
        """`agent_id="alfred"` without any worker-form fields
        populated is Alfred-form. Alfred filing his own onward
        escalation passes `escalation_target="operator"` explicitly;
        that's handled by the escalation_target branch of the
        predicate, not by alfred-as-agent-id.
        """
        assert not is_worker_form(
            agent_id="alfred",
            escalation_target=None,
            gap=None,
            workaround_used=None,
        )

    def test_worker_agent_id_triggers(self):
        assert is_worker_form(
            agent_id="scout",
            escalation_target=None,
            gap=None,
            workaround_used=None,
        )

    def test_escalation_target_alfred_triggers(self):
        """Even without agent_id, an explicit
        escalation_target=alfred marks the filing as worker form so
        the missing-agent-id case fires a clarifying error.
        """
        assert is_worker_form(
            agent_id=None,
            escalation_target="alfred",
            gap=None,
            workaround_used=None,
        )

    def test_gap_alone_triggers(self):
        assert is_worker_form(
            agent_id=None,
            escalation_target=None,
            gap="no capability for X",
            workaround_used=None,
        )

    def test_workaround_alone_triggers(self):
        assert is_worker_form(
            agent_id=None,
            escalation_target=None,
            gap=None,
            workaround_used="manually did Y",
        )

    def test_whitespace_only_gap_does_not_trigger(self):
        """Pure-whitespace populated fields are treated as absent —
        a worker who types `--gap " "` shouldn't accidentally
        activate the worker form.
        """
        assert not is_worker_form(
            agent_id=None,
            escalation_target=None,
            gap="   ",
            workaround_used=None,
        )

    def test_agent_id_case_insensitive(self):
        """`--agent-id Scout` (capital S) still triggers worker form.
        The downstream filename prefix and DB-stored values
        lowercase per WORKER_AGENT_IDS canonical form.
        """
        assert is_worker_form(
            agent_id="Scout",
            escalation_target=None,
            gap=None,
            workaround_used=None,
        )


# ---- validate_worker_form ---------------------------------------------------


class TestValidateWorkerForm:
    def test_complete_worker_form_passes(self):
        validate_worker_form(
            agent_id="scout",
            gap="no capability for X",
            workaround_used="did Y manually",
        )  # no raise

    def test_missing_gap_raises(self):
        with pytest.raises(WorkerFormError) as exc_info:
            validate_worker_form(
                agent_id="scout",
                gap=None,
                workaround_used="did Y manually",
            )
        assert exc_info.value.missing_fields == ("--gap",)

    def test_missing_workaround_raises(self):
        with pytest.raises(WorkerFormError) as exc_info:
            validate_worker_form(
                agent_id="scout",
                gap="no capability for X",
                workaround_used=None,
            )
        assert exc_info.value.missing_fields == ("--workaround",)

    def test_missing_both_surfaces_both_in_one_error(self):
        """Single-pass validation reports ALL missing fields at once
        rather than first-failing — the operator gets the complete
        list and can fix everything in one re-invocation.
        """
        with pytest.raises(WorkerFormError) as exc_info:
            validate_worker_form(
                agent_id="scout",
                gap=None,
                workaround_used=None,
            )
        assert set(exc_info.value.missing_fields) == {"--gap", "--workaround"}

    def test_whitespace_only_treated_as_missing(self):
        with pytest.raises(WorkerFormError):
            validate_worker_form(
                agent_id="scout",
                gap="   ",
                workaround_used="ok",
            )


# ---- infer_escalation_target -----------------------------------------------


class TestInferEscalationTarget:
    @pytest.mark.parametrize("worker", sorted(WORKER_AGENT_IDS))
    def test_worker_codename_infers_alfred(self, worker):
        assert infer_escalation_target(worker) == "alfred"

    def test_alfred_infers_none(self):
        """Alfred-as-filer has no auto-routing target — Alfred's own
        onward escalations specify --escalation-target explicitly.
        """
        assert infer_escalation_target("alfred") is None

    def test_none_infers_none(self):
        assert infer_escalation_target(None) is None

    def test_unknown_infers_none(self):
        """Unknown agent_ids fall through to None rather than raising.
        The CLI catches unknown codenames at the _resolve_agent_id
        gate before this function is called; if a bypass ever
        surfaces, the None return is the safer default than raising.
        """
        assert infer_escalation_target("unknown-codename") is None

    def test_case_insensitive(self):
        assert infer_escalation_target("Scout") == "alfred"
        assert infer_escalation_target("SCOUT") == "alfred"


# ---- worker_filename_prefix ------------------------------------------------


class TestWorkerFilenamePrefix:
    @pytest.mark.parametrize("worker", sorted(WORKER_AGENT_IDS))
    def test_worker_codename_returns_prefix(self, worker):
        assert worker_filename_prefix(worker) == f"worker-{worker}"

    def test_alfred_returns_none(self):
        """Alfred-form filings keep the bare slug filename per
        CLAUDE.md §6 convention.
        """
        assert worker_filename_prefix("alfred") is None

    def test_none_returns_none(self):
        assert worker_filename_prefix(None) is None

    def test_case_insensitive_lookup(self):
        assert worker_filename_prefix("Scout") == "worker-scout"


# ---- Category-agnostic fixture --------------------------------------------


class TestCategoryAgnosticism:
    """Items-5+6 scope clarification: the escalation surface is
    neutral across MCP / CLI / HTTP / skill / operator-defined
    categories. The escalation primitives MUST NOT implicitly
    assume MCP-shape filings. Fixture exercises a skill-request
    worker form end-to-end through the routing predicates.
    """

    def test_skill_request_worker_form_validates(self):
        """A worker filing a request for a SKILL (not an MCP server)
        with the worker form populated must pass validation cleanly.
        The escalation module makes no category-aware assertions.
        """
        validate_worker_form(
            agent_id="scout",
            gap="no installed skill captures our brand-voice review patterns",
            workaround_used="did the review manually from memory",
        )  # no raise; category never inspected

    def test_skill_request_is_recognized_as_worker_form(self):
        assert is_worker_form(
            agent_id="scout",
            escalation_target=None,
            gap="no skill loaded for review patterns",
            workaround_used="reviewed manually",
        )

    def test_skill_request_infers_alfred_route(self):
        """The auto-infer doesn't care what category the request is
        about — `scout → alfred` regardless of MCP / CLI / skill.
        """
        assert infer_escalation_target("scout") == "alfred"
