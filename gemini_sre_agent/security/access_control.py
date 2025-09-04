"""Role-based access control system for provider configuration."""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """System permissions."""

    # Provider permissions
    PROVIDER_READ = "provider:read"
    PROVIDER_WRITE = "provider:write"
    PROVIDER_DELETE = "provider:delete"
    PROVIDER_CONFIGURE = "provider:configure"

    # Configuration permissions
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"
    CONFIG_DELETE = "config:delete"

    # Key management permissions
    KEY_READ = "key:read"
    KEY_WRITE = "key:write"
    KEY_ROTATE = "key:rotate"
    KEY_DELETE = "key:delete"

    # Audit permissions
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"

    # Compliance permissions
    COMPLIANCE_READ = "compliance:read"
    COMPLIANCE_GENERATE = "compliance:generate"

    # Admin permissions
    ADMIN_ALL = "admin:all"
    USER_MANAGE = "user:manage"
    ROLE_MANAGE = "role:manage"


class Role(BaseModel):
    """User role model."""

    name: str = Field(..., description="Role name")
    description: str = Field(..., description="Role description")
    permissions: Set[Permission] = Field(
        default_factory=set, description="Role permissions"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class User(BaseModel):
    """User model."""

    user_id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="User email")
    roles: Set[str] = Field(default_factory=set, description="User roles")
    is_active: bool = Field(default=True, description="Whether user is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = Field(default=None)
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional user metadata"
    )


class AccessRequest(BaseModel):
    """Access request model."""

    user_id: str = Field(..., description="User requesting access")
    resource: str = Field(..., description="Resource being accessed")
    action: str = Field(..., description="Action being performed")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = Field(default=None, description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional request metadata"
    )


class AccessController:
    """Role-based access control system."""

    def __init__(self):
        """Initialize the access controller."""
        self._users: Dict[str, User] = {}
        self._roles: Dict[str, Role] = {}
        self._access_log: List[AccessRequest] = []

        # Initialize default roles
        self._initialize_default_roles()

    def _initialize_default_roles(self) -> None:
        """Initialize default system roles."""
        # Admin role - full access
        admin_role = Role(
            name="admin",
            description="System administrator with full access",
            permissions={
                Permission.ADMIN_ALL,
                Permission.USER_MANAGE,
                Permission.ROLE_MANAGE,
                Permission.PROVIDER_READ,
                Permission.PROVIDER_WRITE,
                Permission.PROVIDER_DELETE,
                Permission.PROVIDER_CONFIGURE,
                Permission.CONFIG_READ,
                Permission.CONFIG_WRITE,
                Permission.CONFIG_DELETE,
                Permission.KEY_READ,
                Permission.KEY_WRITE,
                Permission.KEY_ROTATE,
                Permission.KEY_DELETE,
                Permission.AUDIT_READ,
                Permission.AUDIT_EXPORT,
                Permission.COMPLIANCE_READ,
                Permission.COMPLIANCE_GENERATE,
            },
        )
        self._roles["admin"] = admin_role

        # Operator role - operational access
        operator_role = Role(
            name="operator",
            description="System operator with operational access",
            permissions={
                Permission.PROVIDER_READ,
                Permission.PROVIDER_CONFIGURE,
                Permission.CONFIG_READ,
                Permission.KEY_READ,
                Permission.AUDIT_READ,
                Permission.COMPLIANCE_READ,
            },
        )
        self._roles["operator"] = operator_role

        # Viewer role - read-only access
        viewer_role = Role(
            name="viewer",
            description="Read-only access to system information",
            permissions={
                Permission.PROVIDER_READ,
                Permission.CONFIG_READ,
                Permission.AUDIT_READ,
                Permission.COMPLIANCE_READ,
            },
        )
        self._roles["viewer"] = viewer_role

        # Key manager role - key management access
        key_manager_role = Role(
            name="key_manager",
            description="API key management access",
            permissions={
                Permission.KEY_READ,
                Permission.KEY_WRITE,
                Permission.KEY_ROTATE,
                Permission.PROVIDER_READ,
                Permission.CONFIG_READ,
            },
        )
        self._roles["key_manager"] = key_manager_role

    def create_user(
        self,
        user_id: str,
        username: str,
        email: str,
        roles: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> User:
        """Create a new user.

        Args:
            user_id: Unique user identifier
            username: Username
            email: User email
            roles: List of role names
            metadata: Additional user metadata

        Returns:
            Created user object

        Raises:
            ValueError: If user already exists or roles are invalid
        """
        if user_id in self._users:
            raise ValueError(f"User {user_id} already exists")

        # Validate roles
        if roles:
            for role_name in roles:
                if role_name not in self._roles:
                    raise ValueError(f"Role {role_name} does not exist")

        user = User(
            user_id=user_id,
            username=username,
            email=email,
            roles=set(roles) if roles else set(),
            metadata=metadata or {},
        )

        self._users[user_id] = user
        logger.info(f"Created user: {user_id}")

        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        return self._users.get(user_id)

    def update_user(
        self,
        user_id: str,
        username: Optional[str] = None,
        email: Optional[str] = None,
        roles: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[User]:
        """Update a user.

        Args:
            user_id: User ID to update
            username: New username
            email: New email
            roles: New roles list
            is_active: New active status
            metadata: New metadata

        Returns:
            Updated user object or None if not found
        """
        user = self._users.get(user_id)
        if not user:
            return None

        if username is not None:
            user.username = username
        if email is not None:
            user.email = email
        if roles is not None:
            # Validate roles
            for role_name in roles:
                if role_name not in self._roles:
                    raise ValueError(f"Role {role_name} does not exist")
            user.roles = set(roles)
        if is_active is not None:
            user.is_active = is_active
        if metadata is not None:
            user.metadata.update(metadata)

        logger.info(f"Updated user: {user_id}")
        return user

    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        if user_id in self._users:
            del self._users[user_id]
            logger.info(f"Deleted user: {user_id}")
            return True
        return False

    def create_role(
        self,
        name: str,
        description: str,
        permissions: Optional[List[Permission]] = None,
    ) -> Role:
        """Create a new role.

        Args:
            name: Role name
            description: Role description
            permissions: List of permissions

        Returns:
            Created role object

        Raises:
            ValueError: If role already exists
        """
        if name in self._roles:
            raise ValueError(f"Role {name} already exists")

        role = Role(
            name=name,
            description=description,
            permissions=set(permissions) if permissions else set(),
        )

        self._roles[name] = role
        logger.info(f"Created role: {name}")

        return role

    def get_role(self, name: str) -> Optional[Role]:
        """Get a role by name."""
        return self._roles.get(name)

    def update_role(
        self,
        name: str,
        description: Optional[str] = None,
        permissions: Optional[List[Permission]] = None,
    ) -> Optional[Role]:
        """Update a role.

        Args:
            name: Role name to update
            description: New description
            permissions: New permissions list

        Returns:
            Updated role object or None if not found
        """
        role = self._roles.get(name)
        if not role:
            return None

        if description is not None:
            role.description = description
        if permissions is not None:
            role.permissions = set(permissions)

        role.updated_at = datetime.utcnow()
        logger.info(f"Updated role: {name}")

        return role

    def delete_role(self, name: str) -> bool:
        """Delete a role.

        Args:
            name: Role name to delete

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If role is in use by users
        """
        if name not in self._roles:
            return False

        # Check if role is in use
        users_with_role = [user for user in self._users.values() if name in user.roles]
        if users_with_role:
            raise ValueError(
                f"Cannot delete role {name}: in use by {len(users_with_role)} users"
            )

        del self._roles[name]
        logger.info(f"Deleted role: {name}")
        return True

    def check_permission(
        self,
        user_id: str,
        permission: Permission,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """Check if a user has a specific permission.

        Args:
            user_id: User ID
            permission: Permission to check
            resource: Resource being accessed
            action: Action being performed
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            True if permission is granted, False otherwise
        """
        user = self._users.get(user_id)
        if not user or not user.is_active:
            self._log_access_attempt(
                user_id,
                resource or "unknown",
                action or "unknown",
                False,
                ip_address,
                user_agent,
            )
            return False

        # Check if user has admin permission
        if Permission.ADMIN_ALL in self._get_user_permissions(user):
            self._log_access_attempt(
                user_id,
                resource or "unknown",
                action or "unknown",
                True,
                ip_address,
                user_agent,
            )
            return True

        # Check specific permission
        user_permissions = self._get_user_permissions(user)
        has_permission = permission in user_permissions

        self._log_access_attempt(
            user_id,
            resource or "unknown",
            action or "unknown",
            has_permission,
            ip_address,
            user_agent,
        )

        return has_permission

    def _get_user_permissions(self, user: User) -> Set[Permission]:
        """Get all permissions for a user."""
        permissions = set()

        for role_name in user.roles:
            role = self._roles.get(role_name)
            if role:
                permissions.update(role.permissions)

        return permissions

    def _log_access_attempt(
        self,
        user_id: str,
        resource: str,
        action: str,
        granted: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log an access attempt."""
        access_request = AccessRequest(
            user_id=user_id,
            resource=resource,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"granted": granted},
        )

        self._access_log.append(access_request)

        # Keep only recent access logs (last 1000 entries)
        if len(self._access_log) > 1000:
            self._access_log = self._access_log[-1000:]

    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """Get all permissions for a user."""
        user = self._users.get(user_id)
        if not user or not user.is_active:
            return set()

        return self._get_user_permissions(user)

    def get_users_with_permission(self, permission: Permission) -> List[User]:
        """Get all users who have a specific permission."""
        users = []

        for user in self._users.values():
            if user.is_active and permission in self._get_user_permissions(user):
                users.append(user)

        return users

    def get_access_log(
        self,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        granted: Optional[bool] = None,
        limit: int = 100,
    ) -> List[AccessRequest]:
        """Get access log entries with optional filtering."""
        entries = self._access_log.copy()

        # Apply filters
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        if resource:
            entries = [e for e in entries if e.resource == resource]
        if action:
            entries = [e for e in entries if e.action == action]
        if granted is not None:
            entries = [e for e in entries if e.metadata.get("granted") == granted]

        # Sort by timestamp (newest first)
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        return entries[:limit]

    def get_access_statistics(self) -> Dict[str, Any]:
        """Get access control statistics."""
        if not self._access_log:
            return {}

        total_attempts = len(self._access_log)
        granted_attempts = sum(
            1 for e in self._access_log if e.metadata.get("granted", False)
        )
        denied_attempts = total_attempts - granted_attempts

        # Count by user
        user_counts = {}
        for entry in self._access_log:
            user_counts[entry.user_id] = user_counts.get(entry.user_id, 0) + 1

        # Count by resource
        resource_counts = {}
        for entry in self._access_log:
            resource_counts[entry.resource] = resource_counts.get(entry.resource, 0) + 1

        # Count by action
        action_counts = {}
        for entry in self._access_log:
            action_counts[entry.action] = action_counts.get(entry.action, 0) + 1

        return {
            "total_attempts": total_attempts,
            "granted_attempts": granted_attempts,
            "denied_attempts": denied_attempts,
            "grant_rate": (
                granted_attempts / total_attempts if total_attempts > 0 else 0
            ),
            "user_counts": user_counts,
            "resource_counts": resource_counts,
            "action_counts": action_counts,
            "total_users": len(self._users),
            "active_users": sum(1 for u in self._users.values() if u.is_active),
            "total_roles": len(self._roles),
        }

    def list_users(self) -> List[User]:
        """List all users."""
        return list(self._users.values())

    def list_roles(self) -> List[Role]:
        """List all roles."""
        return list(self._roles.values())

    def assign_role(self, user_id: str, role_name: str) -> bool:
        """Assign a role to a user."""
        user = self._users.get(user_id)
        if not user:
            return False

        if role_name not in self._roles:
            return False

        user.roles.add(role_name)
        logger.info(f"Assigned role {role_name} to user {user_id}")
        return True

    def remove_role(self, user_id: str, role_name: str) -> bool:
        """Remove a role from a user."""
        user = self._users.get(user_id)
        if not user:
            return False

        if role_name in user.roles:
            user.roles.remove(role_name)
            logger.info(f"Removed role {role_name} from user {user_id}")
            return True

        return False

    def get_role_users(self, role_name: str) -> List[User]:
        """Get all users with a specific role."""
        if role_name not in self._roles:
            return []

        return [user for user in self._users.values() if role_name in user.roles]
