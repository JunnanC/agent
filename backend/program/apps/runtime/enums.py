"""Canonical M3 runtime and orchestration enumerations.

These values mirror AGENTS.md section 11.5 and are the single implementation
source for the module. Do not add presentation-specific values here.
"""

from enum import StrEnum


class InstanceStatus(StrEnum):
    REQUESTED = "REQUESTED"
    PROVISIONING = "PROVISIONING"
    READY = "READY"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    DESTROYING = "DESTROYING"
    DESTROYED = "DESTROYED"
    FAILED = "FAILED"

    @classmethod
    def allowed_transitions(cls) -> dict["InstanceStatus", frozenset["InstanceStatus"]]:
        return {
            cls.REQUESTED: frozenset({cls.PROVISIONING, cls.FAILED}),
            cls.PROVISIONING: frozenset({cls.READY, cls.FAILED}),
            cls.READY: frozenset({cls.RUNNING, cls.STOPPED, cls.DESTROYING, cls.FAILED}),
            cls.RUNNING: frozenset({cls.STOPPED, cls.DESTROYING, cls.FAILED}),
            cls.STOPPED: frozenset({cls.RUNNING, cls.DESTROYING, cls.FAILED}),
            cls.DESTROYING: frozenset({cls.DESTROYED, cls.FAILED}),
            cls.DESTROYED: frozenset(),
            cls.FAILED: frozenset({cls.PROVISIONING, cls.DESTROYING}),
        }

    def can_transition_to(self, target: "InstanceStatus") -> bool:
        return target in self.allowed_transitions()[self]


class RuntimeType(StrEnum):
    CONTAINER = "CONTAINER"
    VIRTUAL_MACHINE = "VIRTUAL_MACHINE"


class InstanceProvisioningJobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"


class InstanceProvisioningStepCode(StrEnum):
    RESERVE_QUOTA = "RESERVE_QUOTA"
    CREATE_RUNTIME = "CREATE_RUNTIME"
    MOUNT_MATERIALS = "MOUNT_MATERIALS"
    APPLY_CLOUD_INIT = "APPLY_CLOUD_INIT"
    INSTALL_DEPENDENCIES = "INSTALL_DEPENDENCIES"
    HEALTH_CHECK = "HEALTH_CHECK"
    ISSUE_ACCESS = "ISSUE_ACCESS"
    SNAPSHOT = "SNAPSHOT"
    DESTROY = "DESTROY"


class InstanceProvisioningStepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class OutboxStatus(StrEnum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    DEAD = "DEAD"


class CompensationFailureStage(StrEnum):
    PROVISIONING = "PROVISIONING"
    ARCHIVING = "ARCHIVING"
    ACCESS_REVOKE = "ACCESS_REVOKE"
    DESTROYING = "DESTROYING"
    QUOTA_RELEASE = "QUOTA_RELEASE"
    OUTBOX_PUBLISH = "OUTBOX_PUBLISH"


class CompensationTargetType(StrEnum):
    INSTANCE = "INSTANCE"
    ASSIGNMENT = "ASSIGNMENT"
    ARCHIVE = "ARCHIVE"
    SESSION = "SESSION"
    QUOTA = "QUOTA"
    OUTBOX_EVENT = "OUTBOX_EVENT"


class CompensationStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    MANUAL = "MANUAL"
    RESOLVED = "RESOLVED"
