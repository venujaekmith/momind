from accounts.models import Role
from dashboards.models import Pregnancy


def build_context(user, message):
    """Build a small, privacy-conscious care context from the signed-in user."""
    pregnancy = None
    mother = None

    if user.role == Role.MOTHER and hasattr(user, "user_mother"):
        mother = user.user_mother
    elif user.role == Role.FATHER and hasattr(user, "user_father"):
        mother = user.user_father.linked_mother

    if mother:
        pregnancy = Pregnancy.objects.filter(mother=mother, is_active=True).order_by("-created_at").first()
        if not pregnancy:
            pregnancy = Pregnancy.objects.filter(mother=mother).order_by("-created_at").first()

    phase = "general maternal care"
    week = "not available"
    delivery_date = "not available"
    if pregnancy:
        week = pregnancy.get_pregnancy_week() or "not available"
        if pregnancy.status in {"delivered", "completed"}:
            phase = "postpartum"
            delivery_date = pregnancy.actual_delivery_date or "not available"
        else:
            phase = "pregnancy"
            delivery_date = pregnancy.expected_delivery_date or "not available"

    return {
        "role": user.get_role_display() if user.role else "User",
        "week": week,
        "phase": phase,
        "delivery_date": str(delivery_date),
        "message": message,
    }
