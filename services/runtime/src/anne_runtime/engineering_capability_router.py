from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class EngineeringCapabilityRequest:
    """Describes the engineering capability the planner is trying to satisfy."""

    capability: str
    engineering_domain: str | None = None
    execution_type: str | None = None
    required_software: tuple[str, ...] = ()
    available_software: tuple[str, ...] = ()
    input_artifact_types: tuple[str, ...] = ()
    output_artifact_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.capability.strip():
            raise ValueError("Engineering capability cannot be blank.")

        if self.engineering_domain is not None and not self.engineering_domain.strip():
            raise ValueError("Engineering domain cannot be blank.")

        if self.execution_type is not None and not self.execution_type.strip():
            raise ValueError("Execution type cannot be blank.")


@dataclass(frozen=True)
class EngineeringCapabilityCandidate:
    """A model-safe routing candidate.

    This object intentionally contains no permissions, timeout, retry,
    idempotency, or other execution-authority information.
    """

    tool_id: str
    version: str
    description: str
    engineering_domain: str | None
    execution_type: str
    required_software: tuple[str, ...]
    input_artifact_types: tuple[str, ...]
    output_artifact_types: tuple[str, ...]
    score: int
    match_reasons: tuple[str, ...]


class EngineeringCapabilityRouter:
    """Selects engineering capability candidates from the sanitized catalog."""

    _DOMAIN_SCORE = 40
    _EXECUTION_TYPE_SCORE = 20
    _SOFTWARE_SCORE = 25
    _INPUT_ARTIFACT_SCORE = 15
    _OUTPUT_ARTIFACT_SCORE = 15

    def __init__(
        self,
        catalog: tuple[Mapping[str, object], ...]
        | list[Mapping[str, object]],
    ) -> None:
        self._catalog = tuple(catalog)

    def route(
        self,
        request: EngineeringCapabilityRequest,
    ) -> tuple[EngineeringCapabilityCandidate, ...]:
        candidates: list[EngineeringCapabilityCandidate] = []

        available_software = set(request.available_software)

        for entry in self._catalog:
            capabilities = self._string_tuple(entry.get("capabilities"))

            if request.capability not in capabilities:
                continue

            execution_type = str(entry.get("execution_type", "native"))
            required_software = self._string_tuple(
                entry.get("required_software")
            )

            requested_software = set(request.required_software)

            # The requested software must be satisfied by the candidate.
            # This describes task requirements, not execution authority.
            if not requested_software.issubset(set(required_software)):
                continue

            # External software prerequisites must also be available locally.
            if request.available_software:
                if not set(required_software).issubset(available_software):
                    continue

            score = 0
            reasons: list[str] = []

            engineering_domain = self._optional_string(
                entry.get("engineering_domain")
            )

            if (
                request.engineering_domain is not None
                and engineering_domain == request.engineering_domain
            ):
                score += self._DOMAIN_SCORE
                reasons.append("engineering_domain")

            if (
                request.execution_type is not None
                and execution_type == request.execution_type
            ):
                score += self._EXECUTION_TYPE_SCORE
                reasons.append("execution_type")

            if required_software:
                if request.available_software:
                    score += self._SOFTWARE_SCORE
                    reasons.append("software_available")
            elif not request.available_software:
                reasons.append("native_execution")

            input_artifacts = self._string_tuple(
                entry.get("input_artifact_types")
            )
            output_artifacts = self._string_tuple(
                entry.get("output_artifact_types")
            )

            if request.input_artifact_types:
                requested_inputs = set(request.input_artifact_types)
                matched_inputs = requested_inputs.intersection(input_artifacts)

                if matched_inputs:
                    score += self._INPUT_ARTIFACT_SCORE
                    reasons.append("input_artifact")

            if request.output_artifact_types:
                requested_outputs = set(request.output_artifact_types)
                matched_outputs = requested_outputs.intersection(
                    output_artifacts
                )

                if matched_outputs:
                    score += self._OUTPUT_ARTIFACT_SCORE
                    reasons.append("output_artifact")

            candidates.append(
                EngineeringCapabilityCandidate(
                    tool_id=str(entry["tool_id"]),
                    version=str(entry["version"]),
                    description=str(entry["description"]),
                    engineering_domain=engineering_domain,
                    execution_type=execution_type,
                    required_software=required_software,
                    input_artifact_types=input_artifacts,
                    output_artifact_types=output_artifacts,
                    score=score,
                    match_reasons=tuple(reasons),
                )
            )

        return tuple(
            sorted(
                candidates,
                key=lambda candidate: (-candidate.score, candidate.tool_id),
            )
        )

    def as_model_metadata(self) -> str:
        """Serialize ranked engineering candidates for the model boundary.

        This output intentionally contains routing information only.
        It never exposes permissions, timeout, retry, idempotency, policy,
        or other execution-authority information.
        """
        capabilities = sorted(
            {
                capability
                for entry in self._catalog
                for capability in self._string_tuple(
                    entry.get("capabilities")
                )
                if capability.startswith("engineering.")
            }
        )

        payload: dict[str, list[dict[str, object]]] = {}

        for capability in capabilities:
            candidates = self.route(
                EngineeringCapabilityRequest(
                    capability=capability,
                )
            )

            payload[capability] = [
                {
                    "tool_id": candidate.tool_id,
                    "version": candidate.version,
                    "description": candidate.description,
                    "engineering_domain": candidate.engineering_domain,
                    "execution_type": candidate.execution_type,
                    "required_software": list(candidate.required_software),
                    "input_artifact_types": list(
                        candidate.input_artifact_types
                    ),
                    "output_artifact_types": list(
                        candidate.output_artifact_types
                    ),
                    "score": candidate.score,
                    "match_reasons": list(candidate.match_reasons),
                }
                for candidate in candidates
            ]

        import json

        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _string_tuple(value: object) -> tuple[str, ...]:
        if value is None:
            return ()

        if isinstance(value, (list, tuple)):
            return tuple(str(item) for item in value)

        return ()

    @staticmethod
    def _optional_string(value: object) -> str | None:
        if value is None:
            return None

        return str(value)
