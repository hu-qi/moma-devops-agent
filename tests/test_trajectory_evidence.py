"""C10: canonical trajectory persistence and evidence verification."""

import asyncio
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from devopspilot.contracts.delivery import DeliveryState, DeliveryTask
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef
from devopspilot.contracts.trajectory import DeliveryTrajectory, TrajectoryEvent, TrajectoryEventKind
from devopspilot.trajectory.persistent_store import FileTrajectoryStore, TrajectoryEvidenceError


def _repo_and_task() -> tuple[RepositoryRef, WorkItemRef]:
    repo = RepositoryRef(provider_id="mock", repository_id="r1", full_name="org/repo")
    item = WorkItemRef(repository=repo, item_id="42", title="t")
    return repo, item


def test_trajectory_store_roundtrip(tmp_path: Path) -> None:
    store = FileTrajectoryStore(tmp_path / "trajectories")
    traj = DeliveryTrajectory(
        trajectory_id="traj-1",
        task_id="42",
        repository="org/repo",
        events=(
            TrajectoryEvent(sequence=1, kind=TrajectoryEventKind.ROUTING, name="model.invoke", status="success",
                            attributes={"input_tokens": 10, "output_tokens": 5}),
            TrajectoryEvent(sequence=2, kind=TrajectoryEventKind.TOOL, name="git.commit", status="success"),
        ),
    )
    saved_path = asyncio.run(store.save(traj))
    assert saved_path.is_file()
    loaded = asyncio.run(store.load("traj-1"))
    assert loaded.trajectory_id == "traj-1"
    assert loaded.task_id == "42"
    assert len(loaded.events) == 2
    assert loaded.input_tokens == 10
    print("TRAJECTORY_STORE_ROUNDTRIP_OK")


def test_verifier_rejects_missing_trajectory_evidence(tmp_path: Path) -> None:
    from devopspilot.contracts.delivery import (
        DeliveryPhase, ExecutionResult, VerificationResult,
    )
    from devopspilot.contracts.review import ReviewResult, ReviewVerdict
    from devopspilot.orchestration.verifier import StandardDeliveryVerifier

    repo, item = _repo_and_task()
    task = DeliveryTask(repository=repo, work_item=item, target_branch="main")
    exec_res = ExecutionResult(
        source_branch="b", commit_sha="abc123", summary="s", published=True,
        review=ReviewResult(reviewer_id="r1", verdict=ReviewVerdict.APPROVED,
                            diff_digest=ReviewResult.calculate_diff_digest("d")),
        metadata={
            "trajectory_id": "traj-ghost",
            "trajectory_event_count": "3",
            "capture_issues": "0",
        },
    )
    state = DeliveryState(
        task=task,
        phase=DeliveryPhase.CI_PASSED,
        execution=exec_res,
        verification=VerificationResult(accepted=False, summary=""),
    )
    # fake a passing CI run by binding sha
    from devopspilot.contracts.providers import CIRunRef
    ci = CIRunRef(provider_id="mock", run_id="r1", repository=repo, status="completed",
                  conclusion="success", commit_sha="abc123")
    state = DeliveryState(task=task, phase=DeliveryPhase.CI_PASSED, execution=exec_res, ci_run=ci,
                          verification=VerificationResult(accepted=False, summary=""))

    store = FileTrajectoryStore(tmp_path / "trajectories")
    verifier = StandardDeliveryVerifier(trajectory_store=store)
    result = asyncio.run(verifier.verify(state))
    assert not result.accepted
    assert result.outcome_status.value == "evidence_incomplete"
    assert "not verifiable" in result.summary
    print("VERIFIER_REJECTS_MISSING_TRAJECTORY_OK")


def test_verifier_rejects_count_and_task_mismatch(tmp_path: Path) -> None:
    from devopspilot.contracts.delivery import (
        DeliveryPhase, ExecutionResult, VerificationResult,
    )
    from devopspilot.contracts.providers import CIRunRef
    from devopspilot.contracts.review import ReviewResult, ReviewVerdict
    from devopspilot.orchestration.verifier import StandardDeliveryVerifier

    repo, item = _repo_and_task()
    store = FileTrajectoryStore(tmp_path / "trajectories")

    # Saved trajectory has 2 events and task_id "42"
    traj = DeliveryTrajectory(
        trajectory_id="traj-x", task_id="42", repository="org/repo",
        events=(
            TrajectoryEvent(sequence=1, kind=TrajectoryEventKind.AGENT, name="a", status="ok"),
            TrajectoryEvent(sequence=2, kind=TrajectoryEventKind.TOOL, name="b", status="ok"),
        ),
    )
    asyncio.run(store.save(traj))

    def make_state(event_count: str) -> DeliveryState:
        exec_res = ExecutionResult(
            source_branch="b", commit_sha="abc", summary="s", published=True,
            review=ReviewResult(reviewer_id="r1", verdict=ReviewVerdict.APPROVED,
                                diff_digest=ReviewResult.calculate_diff_digest("d")),
            metadata={"trajectory_id": "traj-x", "trajectory_event_count": event_count, "capture_issues": "0"},
        )
        ci = CIRunRef(provider_id="mock", run_id="r1", repository=repo, status="completed",
                      conclusion="success", commit_sha="abc")
        return DeliveryState(task=DeliveryTask(repository=repo, work_item=item, target_branch="main"),
                             phase=DeliveryPhase.CI_PASSED, execution=exec_res, ci_run=ci,
                             verification=VerificationResult(accepted=False, summary=""))

    verifier = StandardDeliveryVerifier(trajectory_store=store)
    # count mismatch (metadata claims 3, disk has 2)
    res1 = asyncio.run(verifier.verify(make_state("3")))
    assert not res1.accepted and "mismatch" in res1.summary
    print("VERIFIER_REJECTS_COUNT_MISMATCH_OK")

    # task association mismatch
    other_item = WorkItemRef(repository=repo, item_id="99", title="other")
    exec_res = ExecutionResult(
        source_branch="b", commit_sha="abc", summary="s", published=True,
        review=ReviewResult(reviewer_id="r1", verdict=ReviewVerdict.APPROVED,
                            diff_digest=ReviewResult.calculate_diff_digest("d")),
        metadata={"trajectory_id": "traj-x", "trajectory_event_count": "2", "capture_issues": "0"},
    )
    ci = CIRunRef(provider_id="mock", run_id="r1", repository=repo, status="completed",
                  conclusion="success", commit_sha="abc")
    bad_state = DeliveryState(
        task=DeliveryTask(repository=repo, work_item=other_item, target_branch="main"),
        phase=DeliveryPhase.CI_PASSED, execution=exec_res, ci_run=ci,
        verification=VerificationResult(accepted=False, summary=""),
    )
    res2 = asyncio.run(verifier.verify(bad_state))
    assert not res2.accepted and "does not reference" in res2.summary
    print("VERIFIER_REJECTS_TASK_MISMATCH_OK")


def test_verifier_accepts_matching_saved_trajectory(tmp_path: Path) -> None:
    from devopspilot.contracts.delivery import (
        DeliveryPhase, ExecutionResult, VerificationResult,
    )
    from devopspilot.contracts.providers import CIRunRef
    from devopspilot.contracts.review import ReviewResult, ReviewVerdict
    from devopspilot.orchestration.verifier import StandardDeliveryVerifier

    repo, item = _repo_and_task()
    store = FileTrajectoryStore(tmp_path / "trajectories")
    traj = DeliveryTrajectory(
        trajectory_id="traj-ok", task_id="42", repository="org/repo",
        events=(TrajectoryEvent(sequence=1, kind=TrajectoryEventKind.AGENT, name="a", status="ok"),),
    )
    asyncio.run(store.save(traj))

    exec_res = ExecutionResult(
        source_branch="b", commit_sha="abc", summary="s", published=True,
        review=ReviewResult(reviewer_id="r1", verdict=ReviewVerdict.APPROVED,
                            diff_digest=ReviewResult.calculate_diff_digest("d")),
        metadata={"trajectory_id": "traj-ok", "trajectory_event_count": "1", "capture_issues": "0"},
    )
    ci = CIRunRef(provider_id="mock", run_id="r1", repository=repo, status="completed",
                  conclusion="success", commit_sha="abc")
    state = DeliveryState(
        task=DeliveryTask(repository=repo, work_item=item, target_branch="main"),
        phase=DeliveryPhase.CI_PASSED, execution=exec_res, ci_run=ci,
        verification=VerificationResult(accepted=False, summary=""),
    )
    verifier = StandardDeliveryVerifier(trajectory_store=store)
    result = asyncio.run(verifier.verify(state))
    assert result.accepted
    assert any(e.startswith("trajectory_disk:") for e in result.evidence)
    print("VERIFIER_ACCEPTS_SAVED_TRAJECTORY_OK")


def main() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        test_trajectory_store_roundtrip(base / "a")
        test_verifier_rejects_missing_trajectory_evidence(base / "b")
        test_verifier_rejects_count_and_task_mismatch(base / "c")
        test_verifier_accepts_matching_saved_trajectory(base / "d")
    print("ALL C10 TRAJECTORY EVIDENCE TESTS PASSED.")


if __name__ == "__main__":
    main()
