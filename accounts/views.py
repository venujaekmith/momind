from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from .forms import *
from .models import *
from .utility import generate_id
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db import transaction
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme


def save_verification_files(user, files):
    for uploaded_file in files:
        VerifyDoc.objects.create(profile=user, file=uploaded_file)


# -----------------------
# REGISTER
# -----------------------
def register_view(request):
    if request.user.is_authenticated:
        if not request.user.is_role_selected:
            return redirect("accounts:select_role")
        return redirect("dashboards:dashboard")

    form = RegisterForm(request.POST or None)

    if form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("accounts:select_role")

    return render(request, "register.html", {"form": form})


# -----------------------
# LOGIN
# -----------------------
def login_view(request):
    if request.user.is_authenticated:
        if not request.user.is_role_selected:
            return redirect("accounts:select_role")
        return redirect("dashboards:dashboard")

    next_url = request.POST.get("next") or request.GET.get("next")
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            if not user.is_role_selected:
                return redirect("accounts:select_role")

            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect('dashboards:dashboard')
        else:
            # Add error message if authentication fails
            messages.error(request, "Invalid username or password. Please try again.")

    return render(request, "login.html", {"next": next_url or ""})

@require_POST
def logout_view(request):
    logout(request)
    return redirect("accounts:login")

# -----------------------
# ROLE SELECTION
# -----------------------
@login_required
def select_role(request):
    if request.user.is_role_selected:
        return redirect("dashboards:dashboard")

    if request.method == "POST":
        role = request.POST.get("role")
        user = request.user
        valid_roles = {choice for choice, _ in Role.choices}
        if role not in valid_roles:
            messages.error(request, "Please select a valid role.")
            return render(request, "select_role.html", status=400)
        hospital_name = request.POST.get("hospital_name", "").strip()
        if role == Role.HOSPITAL and not hospital_name:
            messages.error(request, "Hospital name is required.")
            return render(request, "select_role.html", status=400)
        try:
            with transaction.atomic():
                destinations = {
                    Role.MOTHER: ("mother_details", MotherProfile, "mother_id", "M"),
                    Role.FATHER: ("father_details", FatherProfile, "father_id", "F"),
                    Role.MIDWIFE: ("midwife_details", MidwifeProfile, "midwife_id", "MW"),
                    Role.DOCTOR: ("doctor_details", DoctorProfile, "doctor_id", "DR"),
                    Role.HOSPITAL_STAFF: (
                        "hospital_staff_details", HospitalStaffProfile, "staff_id", "HS"
                    ),
                }
                if role == Role.HOSPITAL:
                    HospitalProfile.objects.create(
                        user=user,
                        hospital_id=generate_id("H"),
                        name=hospital_name,
                    )
                    destination = "hospital_details"
                else:
                    destination, model, id_field, prefix = destinations[role]
                    model.objects.create(user=user, **{id_field: generate_id(prefix)})

                user.role = role
                user.is_role_selected = True
                user.save(update_fields=["role", "is_role_selected"])
            return redirect(f"accounts:{destination}")
        except (IntegrityError, KeyError):
            messages.error(request, "Error creating profile. Please try again.")
            return render(request, "select_role.html", status=400)


    return render(request, "select_role.html")



@login_required
def mother_details(request):
    if request.user.role != Role.MOTHER:
        return HttpResponseForbidden("This page is only available to mothers.")
    profile, _ = MotherProfile.objects.get_or_create(
        user=request.user,
        defaults={"mother_id": generate_id("M")},
    )
    
    if request.method == "POST":
        form = MotherDetailsForm(request.POST, instance=getattr(request.user, 'details', None))
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.mother = profile
            obj.save()
            return redirect("dashboards:dashboard")
    else:
        form = MotherDetailsForm(instance=getattr(request.user, 'details', None))

    return render(request, "mother_details.html", {"form": form})


@login_required
def father_details(request):
    if request.user.role != Role.FATHER:
        return HttpResponseForbidden("This page is only available to fathers.")
    profile, _ = FatherProfile.objects.get_or_create(
        user=request.user,
        defaults={"father_id": generate_id("F")},
    )
    
    if request.method == "POST":
        form = FatherDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("dashboards:dashboard")
    else:
        form = FatherDetailsForm(instance=profile)

    return render(request, "father_details.html", {"form": form})


@login_required
def midwife_details(request):
    if request.user.role != Role.MIDWIFE:
        return HttpResponseForbidden("This page is only available to midwives.")
    profile, _ = MidwifeProfile.objects.get_or_create(
        user=request.user,
        defaults={"midwife_id": generate_id("MW")},
    )
    
    if request.method == "POST":
        form = MidwifeDetailsForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            save_verification_files(request.user, request.FILES.getlist("attachments"))
            return redirect("dashboards:dashboard")
    else:
        form = MidwifeDetailsForm(instance=profile)

    return render(request, "midwife_details.html", {"form": form})


@login_required
def doctor_details(request):
    if request.user.role != Role.DOCTOR:
        return HttpResponseForbidden("This page is only available to doctors.")
    profile, _ = DoctorProfile.objects.get_or_create(
        user=request.user,
        defaults={"doctor_id": generate_id("DR")},
    )
    
    if request.method == "POST":
        form = DoctorDetailsForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            save_verification_files(request.user, request.FILES.getlist("attachments"))
            return redirect("dashboards:dashboard")
    else:
        form = DoctorDetailsForm(instance=profile)

    return render(request, "doctor_details.html", {"form": form})

@login_required
def hospital_staff_details(request):
    if request.user.role != Role.HOSPITAL_STAFF:
        return HttpResponseForbidden("This page is only available to hospital staff.")
    profile, _ = HospitalStaffProfile.objects.get_or_create(
        user=request.user,
        defaults={"staff_id": generate_id("HS")},
    )

    if request.method == "POST":
        form = HospitalStaffDetailsForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            save_verification_files(request.user, request.FILES.getlist("attachments"))
            return redirect("dashboards:dashboard")
    else:
        form = HospitalStaffDetailsForm(instance=profile)

    return render(request, "hospital_staff_details.html", {"form": form})

@login_required
def hospital_details(request):
    if request.user.role != Role.HOSPITAL:
        return HttpResponseForbidden("This page is only available to hospitals.")
    profile, _ = HospitalProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "hospital_id": generate_id("H"),
            "name": request.user.get_full_name() or request.user.username,
        },
    )
    
    if request.method == "POST":
        form = HospitalDetailsForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            save_verification_files(request.user, request.FILES.getlist("attachments"))
            return redirect("dashboards:dashboard")
    else:
        form = HospitalDetailsForm(instance=profile)

    return render(request, "hospital_details.html", {"form": form})
