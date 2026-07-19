from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from .forms import *
from .models import *
from .utility import generate_id
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError

# -----------------------
# REGISTER
# -----------------------
def register_view(request):
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
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            if not user.is_role_selected:
                return redirect("accounts:select_role")

            return redirect('dashboards:dashboard') 
        else:
            # Add error message if authentication fails
            messages.error(request, "Invalid username or password. Please try again.")

    return render(request, "login.html")

def logout_view(request):
    logout(request)
    return render(request, "login.html")

# -----------------------
# ROLE SELECTION
# -----------------------
@login_required
def select_role(request):
    if request.method == "POST":
        role = request.POST.get("role")
        user = request.user

        user.role = role
        user.is_role_selected = True
        user.save()

        try:
            if role == "MOTHER":
                mother = MotherProfile.objects.create(
                user=user,
                mother_id=generate_id("M")
                )
                #mother.generate_qr_code()   # ← Generate QR Code immediately
                return redirect("accounts:mother_details")

            elif role == "FATHER":
                father = FatherProfile.objects.create(
                user=user,
                father_id=generate_id("F")
                )
                #father.generate_qr_code()   # ← Generate QR Code immediately
                return redirect("accounts:father_details")

            elif role == "MIDWIFE":
                midwife = MidwifeProfile.objects.create(
                user=user,
                midwife_id=generate_id("MW")
            )
                #midwife.generate_qr_code()   # ← Generate QR Code immediately
                return redirect("accounts:midwife_details")

            elif role == "DOCTOR":
                doctor = DoctorProfile.objects.create(
                user=user,
                doctor_id=generate_id("DR")
            )
                #doctor.generate_qr_code()   # ← Generate QR Code immediately
                return redirect("accounts:doctor_details")

            elif role == "HOSPITAL":
                hospital = HospitalProfile.objects.create(
                user=user,
                hospital_id=generate_id("H"),
                name=request.POST.get("hospital_name", "").strip()
            )
                #hospital.generate_qr_code()   # ← Generate QR Code immediately
                return redirect("accounts:hospital_details")

            elif role == "HOSPITAL_STAFF":
                staff = HospitalStaffProfile.objects.create(
                    user=user,
                    staff_id=generate_id("HS")
                )
                return redirect("accounts:hospital_staff_details")

        except Exception as e:
            print("Profile creation error:", e)
            messages.error(request, "Error creating profile. Please try again.")
            return redirect("accounts:register")


    return render(request, "select_role.html")



@login_required
def mother_details(request):
    profile, _ = MotherProfile.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        form = MotherDetailsForm(request.POST, instance=getattr(request.user, 'details', None))
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.mother = profile
            obj.save()
            return redirect("dashboards:dashboard")
    else:
        form = MotherDetailsForm()

    return render(request, "mother_details.html", {"form": form})


@login_required
def father_details(request):
    profile, _ = FatherProfile.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        form = FatherDetailsForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.father = profile
            obj.save()
            return redirect("dashboards:dashboard")
    else:
        form = FatherDetailsForm()

    return render(request, "father_details.html", {"form": form})


@login_required
def midwife_details(request):
    profile, _ = MidwifeProfile.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        form = MidwifeDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("dashboards:dashboard")
    else:
        form = MidwifeDetailsForm(instance=profile)

    return render(request, "midwife_details.html", {"form": form})


@login_required
def doctor_details(request):
    profile, _ = DoctorProfile.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        form = DoctorDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("dashboards:dashboard")
    else:
        form = DoctorDetailsForm(instance=profile)

    return render(request, "doctor_details.html", {"form": form})

@login_required
def hospital_staff_details(request):
    profile, _ = HospitalStaffProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = HospitalStaffDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            return redirect("dashboards:dashboard")
    else:
        form = HospitalStaffDetailsForm(instance=profile)

    return render(request, "hospital_staff_details.html", {"form": form})

@login_required
def hospital_details(request):
    profile, _ = HospitalProfile.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        form = HospitalDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("dashboards:dashboard")
    else:
        form = HospitalDetailsForm(instance=profile)

    return render(request, "hospital_details.html", {"form": form})