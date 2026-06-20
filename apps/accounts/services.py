from django.contrib.auth import get_user_model
from core.exceptions import DomainError, WorkflowError
from .models import UserRole

User = get_user_model()

def create_user(email, password, full_name, role=UserRole.SALES_USER, is_active=True, is_staff=False, is_superuser=False):
    """
    Create a new user in the system.
    """
    if not email:
        raise DomainError("Email address is required.")
    
    if User.objects.filter(email=email).exists():
        raise DomainError(f"A user with email '{email}' already exists.")
        
    if role not in UserRole.values:
        raise DomainError(f"Invalid user role: '{role}'")

    # If the role is ADMIN, make sure they are staff
    staff_status = is_staff or (role == UserRole.ADMIN)

    user = User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name,
        role=role,
        is_active=is_active,
        is_staff=staff_status,
        is_superuser=is_superuser
    )
    return user


def activate_user(user):
    """
    Activate a deactivated user.
    """
    if user.is_active:
        raise WorkflowError("User is already active.")
    user.is_active = True
    user.save()
    return user


def deactivate_user(user):
    """
    Deactivate an active user.
    """
    if not user.is_active:
        raise WorkflowError("User is already inactive.")
    
    # Prevent deactivating the last active admin
    if user.role == UserRole.ADMIN:
        active_admins = User.objects.filter(role=UserRole.ADMIN, is_active=True)
        if active_admins.count() <= 1:
            raise WorkflowError("Cannot deactivate the last active Admin user.")
            
    user.is_active = False
    user.save()
    return user


def change_role(user, new_role):
    """
    Change a user's role.
    """
    if new_role not in UserRole.values:
        raise DomainError(f"Invalid user role: '{new_role}'")
        
    if user.role == new_role:
        raise WorkflowError(f"User is already assigned the '{new_role}' role.")

    # Prevent changing role of the last active admin
    if user.role == UserRole.ADMIN and new_role != UserRole.ADMIN:
        active_admins = User.objects.filter(role=UserRole.ADMIN, is_active=True)
        if active_admins.count() <= 1:
            raise WorkflowError("Cannot change the role of the last active Admin user.")
            
    user.role = new_role
    # Auto-adjust is_staff if they become admin
    if new_role == UserRole.ADMIN:
        user.is_staff = True
    user.save()
    return user
