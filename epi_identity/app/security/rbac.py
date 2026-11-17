"""
Controle de acesso baseado em papéis (RBAC).

Segregação de funções: apenas papéis explicitamente autorizados acessam
dados biométricos. VIEWER, por exemplo, nunca lê embeddings.
"""
from __future__ import annotations

from enum import Enum

from app.enums import Role


class Permission(str, Enum):
    EMPLOYEE_READ = "EMPLOYEE_READ"
    EMPLOYEE_WRITE = "EMPLOYEE_WRITE"
    EMPLOYEE_DELETE = "EMPLOYEE_DELETE"
    BIOMETRIC_ENROLL = "BIOMETRIC_ENROLL"
    BIOMETRIC_READ = "BIOMETRIC_READ"  # acesso a metadados/uso de template
    RECOGNITION_RUN = "RECOGNITION_RUN"
    RECOGNITION_READ = "RECOGNITION_READ"
    REVIEW_DECIDE = "REVIEW_DECIDE"
    AUDIT_READ = "AUDIT_READ"
    CONFIG_WRITE = "CONFIG_WRITE"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),  # todas
    Role.SECURITY_MANAGER: {
        Permission.EMPLOYEE_READ,
        Permission.EMPLOYEE_WRITE,
        Permission.BIOMETRIC_ENROLL,
        Permission.BIOMETRIC_READ,
        Permission.RECOGNITION_RUN,
        Permission.RECOGNITION_READ,
        Permission.REVIEW_DECIDE,
        Permission.AUDIT_READ,
    },
    Role.OPERATOR: {
        Permission.EMPLOYEE_READ,
        Permission.RECOGNITION_RUN,
        Permission.RECOGNITION_READ,
    },
    Role.AUDITOR: {
        Permission.EMPLOYEE_READ,
        Permission.RECOGNITION_READ,
        Permission.AUDIT_READ,
    },
    Role.VIEWER: {
        Permission.EMPLOYEE_READ,
        Permission.RECOGNITION_READ,
    },
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
