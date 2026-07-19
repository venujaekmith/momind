from django.shortcuts import render,redirect,get_object_or_404
from accounts.models import *
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from accounts.models import *
from django.contrib.auth.decorators import login_required
from .models import *
from .utils import *
from django.utils import timezone
from django.db.models import Sum
from accounts.forms import *
from .forums import *
from datetime import timedelta
from ai_services.services.risk_assessment import AdvancedPregnancyRiskService
from postpartum.models import *
import json
from django.conf import settings
from django.urls import reverse

from groq import Groq

# Create your views here.

def get_user_notifications_and_requests(user):
    """
    Get all pending notifications and link requests for a user.
    Returns a dict with 'notifications' and 'pending_link_requests'.
    """
    pending_notifications = Notification.objects.filter(user=user, is_read=False).order_by('-created_at')[:5]
    pending_link_requests = Link_notification.objects.filter(link=user, accepted=False).order_by('-id')
    
    return {
        'notifications': pending_notifications,
        'pending_link_requests': pending_link_requests,
        'unread_count': pending_notifications.count() + pending_link_requests.count(),
    }

def mother_dashboard(request):
    # Ensure the user is a mother
    if request.user.role != "MOTHER":
        return redirect('home') # Or error page
    
    
    mother_profile = request.user.user_mother

    if not Pregnancy.objects.filter(mother=mother_profile).exists():
        return redirect ("dashboards:start_pregnancy")

    mother_details = MotherDetails.objects.get(mother=mother_profile)
    form = MotherDetailsForm(instance=mother_details)
    # Allow selecting a pregnancy via query param ?pregnancy=<id>
    pregnancy_id = request.GET.get('pregnancy')
    pregnancy = None
    if pregnancy_id:
        try:
            pregnancy = Pregnancy.objects.get(id=pregnancy_id, mother=mother_profile)
        except Pregnancy.DoesNotExist:
            pregnancy = None

    # Prefer an active pregnancy; otherwise fall back to the most recent pregnancy
    if not pregnancy:
        pregnancy = Pregnancy.objects.filter(mother=mother_profile, is_active=True).order_by('-created_at').first()
    if not pregnancy:
        pregnancy = Pregnancy.objects.filter(mother=mother_profile).order_by('-created_at').first()
    pregnancies = Pregnancy.objects.filter(mother=mother_profile).order_by('-created_at')
    form_pregnancy = PregnancyForm(instance=pregnancy) if pregnancy else None
    today = timezone.now().date()
    
    if request.method == "POST":
        form = MotherDetailsForm(request.POST, instance=mother_details)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
    else:
        form = MotherDetailsForm(instance=mother_details)

    # 1. Baby Size Data
    baby_info = get_baby_size_info(pregnancy.get_pregnancy_week()) if pregnancy else None
    
    # 2. Daily Water Intake Calculation
    daily_water = WaterIntake.objects.filter(
        mother=mother_profile, 
        timestamp__date=today
    ).aggregate(total=Sum('amount_ml'))['total'] or 0
    
    # 3. Recent Kick Counts
    recent_kicks = KickCount.objects.filter(mother=mother_profile).order_by('-session_start')[:5]

    mother = MotherProfile.objects.get(user=request.user)
    warning = False
    family = 'none'
    if not Family.objects.filter(mother=mother).exists():
            warning = True
    else: 
        family = Family.objects.get(mother=mother)
    
    today = timezone.now().date()
    hospital_queue = []
    hospital_queue_count = 0
    hospital_queue_next = None
    hospital_name = None
    available_clinics = []

    if family != 'none' and getattr(family, 'hospital', None):
        hospital_name = family.hospital.name
        hospital_queue = ScheduleEvent.objects.filter(
            event_type="hospital_clinic",
            scheduled_date=today,
            pregnancy__mother__mom_familiy__hospital=family.hospital
        ).select_related('pregnancy__mother__user').order_by('scheduled_time')
        hospital_queue_count = hospital_queue.count()
        if hospital_queue_count:
            hospital_queue_next = hospital_queue[0]

        available_clinics = Clinics.objects.filter(
            hospital=family.hospital,
            is_active=True,
            date__gte=today
        ).order_by('date', 'time')

    progress_records = PregnancyProgress.objects.filter(pregnancy=pregnancy).order_by("-recorded_at") if pregnancy else PregnancyProgress.objects.none()
    fetal_records = FetalHealth.objects.filter(pregnancy=pregnancy).order_by("-recorded_at") if pregnancy else FetalHealth.objects.none()
    lab_tests = LabTest.objects.filter(pregnancy=pregnancy).order_by("-taken_date") if pregnancy else LabTest.objects.none()
    
    schedule_events = ScheduleEvent.objects.filter(
        pregnancy=pregnancy, 
        scheduled_date__gte=timezone.now().date()
    ).order_by('scheduled_date')[:10] if pregnancy else ScheduleEvent.objects.none()

    trimester_tasks = TrimesterTask.objects.filter(pregnancy=pregnancy) if pregnancy else TrimesterTask.objects.none()

  
    notif_data = get_user_notifications_and_requests(request.user)
    
    context = {
        'profile': mother_profile,
        'mother_details':mother_details,
        'baby_info': baby_info,
        'daily_water': daily_water,
        'recent_kicks': recent_kicks,
        'warning' : warning,
        'family' :family,
        "form": form,
        'pregnancy' : pregnancy,
        'pregnancies': pregnancies,
        "form_pregnancy" :form_pregnancy,
        "progress_records": progress_records,
        "fetal_records": fetal_records,
        "lab_tests": lab_tests,
        'trimester_tasks':trimester_tasks,
        'schedule_events':schedule_events,
        'hospital_queue': hospital_queue,
        'hospital_queue_count': hospital_queue_count,
        'hospital_queue_next': hospital_queue_next,
        'hospital_name': hospital_name,
        'available_clinics': available_clinics,
        'notifications': notif_data['notifications'],
        'pending_link_requests': notif_data['pending_link_requests'],
        'unread_count': notif_data['unread_count'],
    }


    if pregnancy and pregnancy.status in ["delivered", "completed"]:
        context.update({
        'is_postpartum': True,
        'baby': BabyProfile.objects.filter(pregnancy=pregnancy).first(),
        'schedule_events': ScheduleEvent.objects.filter(
            pregnancy=pregnancy, 
            scheduled_date__gte=timezone.now().date()
        ).order_by('scheduled_date')[:15],   # Show upcoming
        })
    else:
        context['is_postpartum'] = False

    return render(request, "mother.html", context)


def clear_previous_pregnancy_data(pregnancy):
    """Clear the previous pregnancy's related data before starting a new one."""
    if not pregnancy:
        return

    pregnancy.progress.all().delete()
    pregnancy.fetal_records.all().delete()
    pregnancy.lab_tests.all().delete()
    pregnancy.schedule_events.all().delete()
    pregnancy.trimester_tasks.all().delete()
    pregnancy.visit_notes.all().delete()
    pregnancy.risks.all().delete()
    pregnancy.vaccinations.all().delete()
    pregnancy.midwife_visits.all().delete()
    pregnancy.milestones.all().delete()
    pregnancy.babies.all().delete()
    pregnancy.alerts.all().delete()
    pregnancy.medication_set.all().delete()

    if hasattr(pregnancy, 'trimester_plan') and pregnancy.trimester_plan:
        pregnancy.trimester_plan.delete()

    PostpartumProfile.objects.filter(pregnancy=pregnancy).delete()


@login_required
def start_pregnancy(request):
    mother_profile = request.user.user_mother

    if Pregnancy.objects.filter(mother=mother_profile, is_active=True).exists():
        messages.warning(request, "You already have an active pregnancy. Please complete it before starting a new one.")
        return redirect("dashboards:dashboard")

    previous_pregnancy = Pregnancy.objects.filter(
        mother=mother_profile,
        status__in=["delivered", "completed"]
    ).order_by('-created_at').first()

    if request.method == "POST":
        form = PregnancyForm(request.POST)
        if form.is_valid():
            if previous_pregnancy:
                clear_previous_pregnancy_data(previous_pregnancy)

            obj = form.save(commit=False)
            obj.mother = mother_profile
            obj.pregnancy_number = Pregnancy.objects.filter(mother=mother_profile).count() + 1
            obj.is_active = True
            obj.save()

            create_default_pregnancy_schedule(obj)
            TrimesterPlan.objects.get_or_create(pregnancy=obj)
            messages.success(request, "New pregnancy started successfully.")
            return redirect("dashboards:dashboard")
    else:
        form = PregnancyForm()

    return render(request, "start.html", {"forum": form})


def father_dashboard(request):
        father = FatherProfile.objects.get(user=request.user)
        family = Family.objects.filter(father=father).first()
        warning = family is None
        
        # Initialize variables as None/0 in case no mother is linked yet
        mother_profile = father.linked_mother
        pregnancy = None
        baby_info = None
        daily_water = 0
        recent_kicks = []
        today = timezone.now().date()
        hospital_queue = []
        hospital_queue_count = 0
        hospital_name = None
        available_clinics = []

        if mother_profile:
            # 1. Baby Size Data
            
            # Select active pregnancy if available, otherwise most recent
            pregnancy = Pregnancy.objects.filter(mother=mother_profile, is_active=True).order_by('-created_at').first()
            if not pregnancy:
                pregnancy = Pregnancy.objects.filter(mother=mother_profile).order_by('-created_at').first()
            pregnancies = Pregnancy.objects.filter(mother=mother_profile).order_by('-created_at')
            if pregnancy:
                baby_info = get_baby_size_info(pregnancy.get_pregnancy_week())
            # 2. Daily Water (Mother's intake)
            daily_water = WaterIntake.objects.filter(
                mother=mother_profile, 
                timestamp__date=today
            ).aggregate(total=Sum('amount_ml'))['total'] or 0
            
            # 3. Recent Kicks
            recent_kicks = KickCount.objects.filter(mother=mother_profile).order_by('-session_start')[:5]
            
            if family and getattr(family, 'hospital', None):
                hospital_name = family.hospital.name
                hospital_queue = ScheduleEvent.objects.filter(
                    event_type="hospital_clinic",
                    scheduled_date=today,
                    pregnancy__mother__mom_familiy__hospital=family.hospital
                ).select_related('pregnancy__mother__user').order_by('scheduled_time')
                hospital_queue_count = hospital_queue.count()
                available_clinics = Clinics.objects.filter(
                    hospital=family.hospital,
                    is_active=True,
                    date__gte=today
                ).order_by('date', 'time')
        
        schedule_events = ScheduleEvent.objects.filter(
            pregnancy=pregnancy, 
            scheduled_date__gte=timezone.now().date()
            ).order_by('scheduled_date')[:10]

        trimester_tasks = TrimesterTask.objects.filter(pregnancy=pregnancy)
       
        notif_data = get_user_notifications_and_requests(request.user)
        
        return render(request, "father.html", {
            'warning': warning,
            'family': family,
            'mother_profile': mother_profile,
            'baby_info': baby_info,
            'daily_water': daily_water,
            'recent_kicks': recent_kicks,
            'pregnancy' : pregnancy,
            'pregnancies': pregnancies if 'pregnancies' in locals() else Pregnancy.objects.none(),
            'trimester_tasks':trimester_tasks,
            'schedule_events':schedule_events,
            'hospital_queue': hospital_queue,
            'hospital_queue_count': hospital_queue_count,
            'hospital_name': hospital_name,
        'available_clinics': available_clinics,
        'notifications': notif_data['notifications'],
        'pending_link_requests': notif_data['pending_link_requests'],
        'unread_count': notif_data['unread_count'],
        })

def log_water(request):
    if request.method == "POST":
        amount = request.POST.get('amount')
        WaterIntake.objects.create(mother=request.user.user_mother, amount_ml=amount)
    return redirect('dashboards:dashboard')

@login_required
def log_kicks(request):
    if request.method == "POST":
        count = request.POST.get('count')
        KickCount.objects.create(mother=request.user.user_mother, count=count)
    return redirect('dashboards:dashboard')


@login_required
def midwife_dashboard(request):
    midwife = get_object_or_404(MidwifeProfile, user=request.user)

    all_pregnancies = Pregnancy.objects.filter(
        mother__mom_familiy__midwife=midwife
    ).select_related('mother__user', 'trimester_plan').order_by('-created_at').distinct()

    active_pregnancies = all_pregnancies.filter(status="ongoing")
    postpartum_pregnancies = all_pregnancies.filter(status__in=["delivered", "completed"])

    upcoming_visits = ScheduleEvent.objects.filter(
        created_by=request.user,
        event_type="midwife_visit",
        scheduled_date__gte=timezone.now().date(),
        scheduled_date__lte=timezone.now().date() + timedelta(weeks=8)
    ).select_related('pregnancy__mother__user').order_by('scheduled_date')

    context = {
        "families": Family.objects.filter(midwife=midwife),
        "active_pregnancies": active_pregnancies,
        "postpartum_pregnancies": postpartum_pregnancies,
        "all_pregnancies": all_pregnancies,
        "upcoming_visits": upcoming_visits,
        "total_active": active_pregnancies.count(),
        "total_postpartum": postpartum_pregnancies.count(),
        "total_pregnancies": all_pregnancies.count(),
    }

    notif_data = get_user_notifications_and_requests(request.user)
    context['notifications'] = notif_data['notifications']
    context['pending_link_requests'] = notif_data['pending_link_requests']
    context['unread_count'] = notif_data['unread_count']

    return render(request, "midwife.html", context)

@login_required
def midwife_mother_detail(request, pregnancy_id):
    pregnancy = get_object_or_404(Pregnancy, id=pregnancy_id)
    
    # Security check (uncomment if needed)
    # if not can_edit_pregnancy(request.user, pregnancy):
    #     messages.error(request, "You are not authorized.")
    #     return redirect('dashboards:dashboard')

    # === Antenatal Records ===
    progress_records = PregnancyProgress.objects.filter(pregnancy=pregnancy).order_by('-recorded_at')
    fetal_records = FetalHealth.objects.filter(pregnancy=pregnancy).order_by('-recorded_at')
    lab_tests = LabTest.objects.filter(pregnancy=pregnancy).order_by('-taken_date')
    weight_logs = WeightLog.objects.filter(mother=pregnancy.mother).order_by('-date')
    kick_counts = KickCount.objects.filter(mother=pregnancy.mother).order_by('-session_start')
    water_intakes = WaterIntake.objects.filter(mother=pregnancy.mother).order_by('-timestamp')
    schedule_events = ScheduleEvent.objects.filter(pregnancy=pregnancy).order_by('scheduled_date')
    visit_notes = VisitNote.objects.filter(pregnancy=pregnancy).order_by('-visit_date')

    # === Postpartum & Baby Data ===
    is_postpartum = pregnancy.status in ["delivered", "completed"]
    is_father = Family.objects.filter(mother=pregnancy.mother, father__user=request.user).exists()
    # Get ALL babies (supports single or multiple)
    babies = BabyProfile.objects.filter(pregnancy=pregnancy).order_by('birth_date', 'name')
    
    # Get development records for ALL babies
    development_records = []
    if babies.exists():
        development_records = BabyDevelopmentRecord.objects.filter(
            baby__in=babies
        ).select_related('baby').order_by('-recorded_at')

    # Postpartum Profile
    postpartum_profile = None
    mood_entries = []
    journal_entries = []
    stress_assessments = []

    if is_postpartum:
        # Prefer a profile attached to the pregnancy, fall back to user-level profiles
        postpartum_profile = getattr(pregnancy, 'postpartum_profile', None) or getattr(pregnancy.mother.user, 'postpartum_profiles', None)
        mood_entries = MoodEntry.objects.filter(user=pregnancy.mother.user).order_by('-date')[:15]
        journal_entries = JournalEntry.objects.filter(user=pregnancy.mother.user).order_by('-date')[:10]
        stress_assessments = AIStressAssessment.objects.filter(user=pregnancy.mother.user).order_by('-created_at')[:10]

    pregnancies = Pregnancy.objects.filter(mother=pregnancy.mother).order_by('-created_at')

    context = {
        'pregnancy': pregnancy,
        'mother': pregnancy.mother,
        'mother_details': getattr(pregnancy.mother, 'mother_details', None),
        
        # Antenatal
        'progress_records': progress_records,
        'fetal_records': fetal_records,
        'lab_tests': lab_tests,
        'weight_logs': weight_logs,
        'kick_counts': kick_counts,
        'water_intakes': water_intakes,
        'schedule_events': schedule_events,
        'visit_notes': visit_notes,
        
        # Postpartum & Babies
        'is_postpartum': is_postpartum,
        'postpartum_profile': postpartum_profile,
        'babies': babies,                    # ← Now multiple babies
        'development_records': development_records,
        'pregnancies': pregnancies,
        
        'mood_entries': mood_entries,
        'journal_entries': journal_entries,
        'stress_assessments': stress_assessments,

        'is_father': is_father,
    }

    return render(request, "mother_detail.html", context)

@login_required
def add_baby_development(request, pregnancy_id):
    pregnancy = get_object_or_404(Pregnancy, id=pregnancy_id)
    baby_id = request.GET.get('baby_id')
    
    if baby_id:
        baby = get_object_or_404(BabyProfile, id=baby_id, pregnancy=pregnancy)
    else:
        # Default to first baby if none specified
        baby = BabyProfile.objects.filter(pregnancy=pregnancy).first()

    if not baby:
        messages.error(request, "No baby found.")
        return redirect('dashboards:midwife_mother_detail', pregnancy_id)

    if request.method == 'POST':
        form = BabyDevelopmentForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.baby = baby
            record.recorded_by = request.user
            record.save()
            messages.success(request, f"Development record added for {baby.name}.")
            return redirect('dashboards:midwife_mother_detail', pregnancy_id)
    else:
        form = BabyDevelopmentForm(initial={'age_in_weeks': baby.get_age_in_weeks()})

    context = {
        'form': form,
        'pregnancy': pregnancy,
        'baby': baby,
        'baby_age': baby.get_age_display(),
    }
    return render(request, 'add_baby_development.html', context)

@login_required
def add_visit_note(request, pregnancy_id):
    pregnancy = Pregnancy.objects.get(id=pregnancy_id)
    
    if request.method == "POST":
        VisitNote.objects.create(
            pregnancy=pregnancy,
            visit_date=timezone.now().date(),
            notes=request.POST.get('notes'),
            findings=request.POST.get('findings'),
            recommendations=request.POST.get('recommendations'),
            recorded_by=request.user,
            scheduled_event_id=request.POST.get('scheduled_event')
        )
        messages.success(request, "Visit note saved successfully.")
        return redirect('dashboards:midwife_mother_detail', pregnancy_id=pregnancy.id)

    # GET
    upcoming = ScheduleEvent.objects.filter(
        pregnancy=pregnancy, 
        event_type="midwife_visit",
        scheduled_date__lte=timezone.now().date() + timedelta(days=7)
    )
    
    return render(request, "add_visit_note.html", {
        'pregnancy': pregnancy,
        'upcoming_events': upcoming
    })

def doctor_dashboard(request):
    doctor = DoctorProfile.objects.get(user=request.user)
    families = Family.objects.filter(doctor=doctor)

    pregnancies = Pregnancy.objects.filter(
        mother__mom_familiy__doctor=doctor
    ).select_related('mother__user').order_by('-created_at').distinct()

    my_appointments = ScheduleEvent.objects.filter(
        created_by=request.user,
        scheduled_date__gte=timezone.now().date()
    ).select_related('pregnancy__mother__user').order_by('scheduled_date')

    notif_data = get_user_notifications_and_requests(request.user)
    
    context = {
        "families": families,
        "pregnancies": pregnancies,
        "my_appointments": my_appointments,
        'notifications': notif_data['notifications'],
        'pending_link_requests': notif_data['pending_link_requests'],
        'unread_count': notif_data['unread_count'],
    }
    return render(request, "doctor.html", context)


def hospital_dashboard(request):
    hospital = HospitalProfile.objects.get(user=request.user)
    families = Family.objects.filter(hospital=hospital)

    pregnancies = Pregnancy.objects.filter(
        mother__mom_familiy__hospital=hospital
    ).select_related('mother__user').order_by('-created_at').distinct()

    today = timezone.now().date()
    today_queue = ScheduleEvent.objects.filter(
        event_type="hospital_clinic",
        scheduled_date=today,
        pregnancy__mother__mom_familiy__hospital=hospital
    ).select_related('pregnancy__mother__user').order_by('scheduled_time')

    hospital_clinics = Clinics.objects.filter(
        hospital=hospital,
        is_active=True
    ).order_by('date', 'time')

    hospital_staff = HospitalStaffProfile.objects.filter(hospital=hospital)

    context = {
        "families": families,
        "pregnancies": pregnancies,
        "hospital_clinics": hospital_clinics,
        "hospital_staff": hospital_staff,
        "today_queue": today_queue,
        "today_queue_count": today_queue.count(),
    }
    
    notif_data = get_user_notifications_and_requests(request.user)
    context['notifications'] = notif_data['notifications']
    context['pending_link_requests'] = notif_data['pending_link_requests']
    context['unread_count'] = notif_data['unread_count']
    
    return render(request, "hospital.html", context)


@login_required
def hospital_staff_dashboard(request):
    staff = get_object_or_404(HospitalStaffProfile, user=request.user)
    hospital = staff.hospital
    today = timezone.now().date()

    assigned_clinics = Clinics.objects.filter(
        hospital=hospital,
        staff=staff,
        is_active=True
    ).order_by('date', 'time')

    today_queue = ScheduleEvent.objects.filter(
        event_type="hospital_clinic",
        clinic__in=assigned_clinics,
        scheduled_date=today
    ).select_related('pregnancy__mother__user').order_by('scheduled_time')

    context = {
        "staff": staff,
        "hospital": hospital,
        "assigned_clinics": assigned_clinics,
        "today_queue": today_queue,
        "today_queue_count": today_queue.count(),
    }
    
    notif_data = get_user_notifications_and_requests(request.user)
    context['notifications'] = notif_data['notifications']
    context['pending_link_requests'] = notif_data['pending_link_requests']
    context['unread_count'] = notif_data['unread_count']
    
    return render(request, "hospital_staff.html", context)


@login_required
def clinic_directory(request):
    clinics = Clinics.objects.filter(
        is_active=True,
        date__gte=timezone.now().date()
    ).select_related('hospital').prefetch_related('staff').order_by('date', 'time')

    return render(request, "clinic_list.html", {
        "clinics": clinics
    })


@login_required
def clinic_detail(request, clinic_id):
    clinic = get_object_or_404(Clinics, id=clinic_id, is_active=True)
    appointments = ScheduleEvent.objects.filter(
        clinic=clinic,
        event_type="hospital_clinic",
        scheduled_date=clinic.date
    ).select_related('pregnancy__mother__user').order_by('scheduled_time')

    return render(request, "clinic_detail.html", {
        "clinic": clinic,
        "appointments": appointments,
        "queue_count": appointments.count(),
    })


@login_required
def create_hospital_clinic(request, clinic_id=None):
    user = request.user
    hospital = None
    if user.role == "HOSPITAL":
        hospital = get_object_or_404(HospitalProfile, user=user)
    elif user.role == "HOSPITAL_STAFF":
        staff = get_object_or_404(HospitalStaffProfile, user=user, is_active=True)
        if not staff.hospital:
            messages.error(request, "You are not assigned to a hospital yet.")
            return redirect('dashboards:dashboard')
        hospital = staff.hospital
    else:
        messages.error(request, "You are not authorized to manage clinics.")
        return redirect('dashboards:dashboard')

    clinic = None
    if clinic_id:
        clinic = get_object_or_404(Clinics, id=clinic_id, hospital=hospital)

    if request.method == "POST":
        form = ClinicForm(request.POST, instance=clinic)
        if form.is_valid():
            clinic = form.save(commit=False)
            clinic.hospital = hospital
            if not clinic.created_by:
                clinic.created_by = user
            clinic.save()
            messages.success(request, f"Clinic session {'updated' if clinic_id else 'created'} successfully.")
            return redirect('dashboards:dashboard')
    else:
        form = ClinicForm(instance=clinic)

    return render(request, "clinic_form.html", {
        "form": form,
        "hospital": hospital,
        "clinic": clinic,
        "is_edit": bool(clinic_id)
    })


@login_required
def assign_clinic_staff(request, clinic_id):
    selected_clinic_id = request.POST.get('clinic_id') or clinic_id
    if request.user.role == "HOSPITAL_STAFF":
        clinic = get_object_or_404(Clinics, id=selected_clinic_id, staff__user=request.user)
    else:
        clinic = get_object_or_404(Clinics, id=selected_clinic_id, hospital__user=request.user)

    if request.method == "POST":
        staff_id = request.POST.get('staff_id')
        try:
            staff = HospitalStaffProfile.objects.get(staff_id=staff_id, hospital=clinic.hospital)
            clinic.staff.add(staff)
            messages.success(request, f"{staff.user.get_full_name() or staff.user.username} assigned to {clinic.name}.")
        except HospitalStaffProfile.DoesNotExist:
            messages.error(request, "Hospital staff not found for this hospital.")
    return redirect('dashboards:dashboard')


@login_required
def add_clinic_appointment(request, clinic_id):
    if request.user.role == "HOSPITAL_STAFF":
        clinic = get_object_or_404(Clinics, id=clinic_id, staff__user=request.user)
    else:
        clinic = get_object_or_404(Clinics, id=clinic_id, hospital__user=request.user)

    if request.method == "POST":
        patient_identifier = request.POST.get('patientID', '').strip()
        if not patient_identifier:
            messages.error(request, "Please enter a valid patient ID.")
            return redirect('dashboards:dashboard')

        pregnancy = None
        mother = MotherProfile.objects.filter(mother_id__iexact=patient_identifier).first()
        if not mother:
            mother = MotherProfile.objects.filter(user__username__iexact=patient_identifier).first()
        if not mother:
            mother = MotherProfile.objects.filter(user__email__iexact=patient_identifier).first()

        if mother:
            family = Family.objects.filter(mother=mother, hospital=clinic.hospital).first()
            if family:
                pregnancy = Pregnancy.objects.filter(
                    mother=mother,
                    is_active=True
                ).order_by('-created_at').first()

        if not pregnancy:
            try:
                pregnancy = Pregnancy.objects.get(
                    id=patient_identifier,
                    mother__mom_familiy__hospital=clinic.hospital
                )
            except (Pregnancy.DoesNotExist, ValueError):
                pregnancy = None

        if not pregnancy:
            messages.error(request, "Patient not found or not assigned to this hospital.")
            return redirect('dashboards:dashboard')

        ScheduleEvent.objects.create(
            pregnancy=pregnancy,
            title=f"{clinic.name} Clinic Appointment",
            event_type="hospital_clinic",
            scheduled_date=clinic.date,
            scheduled_time=clinic.time,
            clinic=clinic,
            location=clinic.location,
            notes=f"Assigned by hospital staff to {clinic.name}.",
            created_by=request.user,
            what_to_bring="Medical records, antenatal card"
        )
        messages.success(request, "Patient added to clinic queue.")

    return redirect('dashboards:dashboard')


def dashboard(request):
    role = request.user.role
    
    if role == "MOTHER":
        return mother_dashboard(request)

    elif role == "FATHER":
        return father_dashboard(request)

    elif role == "MIDWIFE":
        return midwife_dashboard(request)
    
    elif role == "DOCTOR":
        return doctor_dashboard(request)

    elif role == "HOSPITAL":
        return hospital_dashboard(request)

    elif role == "HOSPITAL_STAFF":
        return hospital_staff_dashboard(request)

    return redirect("accounts:login")



def add_member_to_family(user, member_role, member_id,request):
    """
    Links a professional or partner to the user's family using their unique ID.
    """
    # 1. Get the user's family (assumes family is already created via dashboard)
    try:
        if user.role == 'MOTHER':
            family,created = Family.objects.get_or_create(mother=user.user_mother)
        elif user.role == 'FATHER':
            family,created = Family.objects.get_or_create(father=user.user_father)
        else:
            return False, "Only parents can manage family members."
    except Family.DoesNotExist:
        return False, "Family unit not found."

    # 2. Find and Link the member based on role
    try:
        if member_role == 'MOTHER':
            family.mother = MotherProfile.objects.get(mother_id=member_id)
            mother = MotherProfile.objects.get(mother_id=member_id)
            father = user.user_father
            father.linked_mother = mother
            father.save()
            
        elif member_role == 'FATHER':
            family.father = FatherProfile.objects.get(father_id=member_id)
            father = FatherProfile.objects.get(father_id=member_id)
            mother = user.user_mother
            father.linked_mother = mother
            father.save()

        elif member_role == 'MIDWIFE':
            family.midwife = MidwifeProfile.objects.get(midwife_id=member_id)

        elif member_role == 'DOCTOR':
            family.doctor = DoctorProfile.objects.get(doctor_id=member_id)

        elif member_role == 'HOSPITAL':
            family.hospital = HospitalProfile.objects.get(hospital_id=member_id)
        
        family.save()
        return True, f"Successfully added {member_role.lower()}."
        
    except ObjectDoesNotExist:
        return False, f"No {member_role.lower()} found with ID: {member_id}"
    


@login_required
def remove_family_member(request):
    if request.method != 'POST':
        return redirect('dashboards:dashboard')

    family_id = request.POST.get('family_id')
    role = request.POST.get('role')
    family = get_object_or_404(Family, id=family_id)
    user = request.user

    if user.role not in ['MOTHER', 'FATHER']:
        messages.error(request, 'Only parents can edit family membership.')
        return redirect('dashboards:dashboard')

    if user.role == 'MOTHER' and family.mother != getattr(user, 'user_mother', None):
        messages.error(request, 'You can only manage your own family.')
        return redirect('dashboards:dashboard')

    if user.role == 'FATHER' and family.father != getattr(user, 'user_father', None):
        messages.error(request, 'You can only manage your own family.')
        return redirect('dashboards:dashboard')

    if role == 'MOTHER':
        if family.mother:
            family.mother = None
            if family.father:
                family.father.linked_mother = None
                family.father.save()
    elif role == 'FATHER':
        if family.father:
            family.father.linked_mother = None
            family.father.save()
            family.father = None
    elif role == 'MIDWIFE':
        family.midwife = None
    elif role == 'DOCTOR':
        family.doctor = None
    elif role == 'HOSPITAL':
        family.hospital = None
    else:
        messages.error(request, 'Invalid family role.')
        return redirect('dashboards:dashboard')

    family.save()
    messages.success(request, f'{role.capitalize()} removed from family.')
    return redirect('dashboards:dashboard')


@login_required
def leave_family(request, family_id):
    if request.method != 'POST':
        return redirect('dashboards:dashboard')

    family = get_object_or_404(Family, id=family_id)
    user = request.user

    if user.role == 'MIDWIFE':
        if family.midwife is None or family.midwife.user != user:
            messages.error(request, 'You are not assigned to that family.')
            return redirect('dashboards:dashboard')
        family.midwife = None
    elif user.role == 'DOCTOR':
        if family.doctor is None or family.doctor.user != user:
            messages.error(request, 'You are not assigned to that family.')
            return redirect('dashboards:dashboard')
        family.doctor = None
    elif user.role == 'HOSPITAL':
        if family.hospital is None or family.hospital.user != user:
            messages.error(request, 'You are not assigned to that family.')
            return redirect('dashboards:dashboard')
        family.hospital = None
    else:
        messages.error(request, 'Only doctors, midwives, and hospitals can leave a family this way.')
        return redirect('dashboards:dashboard')

    family.save()
    messages.success(request, 'You have left the family.')
    return redirect('dashboards:dashboard')


def link_member_view(request):
    # When a user requests to link someone to their family we create a Link_notification
    # and notify the target user. The actual Family row is updated only after the
    # target accepts via the `respond_link_request` view.
    if request.method == "POST":
        role_to_add = request.POST.get('role')  # e.g., 'MIDWIFE'
        target_id = request.POST.get('target_id')  # e.g., 'MID-12345'

        # Resolve the target user from the provided role and id
        target_user = None
        try:
            if role_to_add == 'MIDWIFE':
                profile = MidwifeProfile.objects.get(midwife_id=target_id)
                target_user = profile.user
            elif role_to_add == 'DOCTOR':
                profile = DoctorProfile.objects.get(doctor_id=target_id)
                target_user = profile.user
            elif role_to_add == 'HOSPITAL':
                profile = HospitalProfile.objects.get(hospital_id=target_id)
                target_user = profile.user
            elif role_to_add == 'MOTHER':
                profile = MotherProfile.objects.get(mother_id=target_id)
                target_user = profile.user
            elif role_to_add == 'FATHER':
                profile = FatherProfile.objects.get(father_id=target_id)
                target_user = profile.user
        except ObjectDoesNotExist:
            messages.error(request, f"No {role_to_add.lower()} found with ID: {target_id}")
            return redirect('dashboards:dashboard')

        # Optional free-text note supplied by requester
        user_note = request.POST.get('note', '')

        # Create a link request record (store both identifier and note)
        link_req = Link_notification.objects.create(
            linker=request.user,
            linker_type=request.user.role,
            link=target_user,
            link_type=role_to_add,
            note=user_note,
            member_identifier=str(target_id),
            accepted=False,
        )

        # Create a user-visible notification for the target
        try:
            accept_url = request.build_absolute_uri(reverse('dashboards:respond_link_request', args=[link_req.id]))
        except Exception:
            accept_url = ''

        message_text = f"{request.user.get_full_name() or request.user.username} has requested to link you to their family as {role_to_add.lower()}"
        if user_note:
            message_text += f" — Message: {user_note}"
        if accept_url:
            message_text += f". Reply here: {accept_url}"

        Notification.objects.create(
            user=target_user,
            title="Family Link Request",
            message=message_text,
        )

        messages.success(request, f"Link request sent to {target_user.get_full_name() or target_user.username}.")

    return redirect('dashboards:dashboard')


@login_required
def respond_link_request(request, link_id):
    """Accept or decline a pending family link request."""
    link_req = get_object_or_404(Link_notification, id=link_id)

    # Only the target user can respond
    if request.user != link_req.link:
        messages.error(request, "You are not authorized to respond to this request.")
        return redirect('dashboards:dashboard')

    action = request.POST.get('action') if request.method == 'POST' else None
    if action == 'accept':
        member_id = link_req.member_identifier or ''
        # Perform the actual linking using the original requester as the family owner
        success, message = add_member_to_family(link_req.linker, link_req.link_type, member_id, request)
        print(success)
        print("===")
        print(message)
        if success:
            link_req.accepted = True
            link_req.save()

            # If midwife was linked, auto-create visits
            if link_req.link_type == 'MIDWIFE':
                try:
                    family = Family.objects.filter(mother=link_req.linker.user_mother).first() if link_req.linker.role == 'MOTHER' else Family.objects.filter(midwife__user=link_req.linker).first()
                    if family and family.midwife:
                        pregnancies = Pregnancy.objects.filter(mother=family.mother, is_active=True)
                        for pregnancy in pregnancies:
                            create_midwife_visits_for_pregnancy(pregnancy, family.midwife)
                except Exception as e:
                    print("Error creating midwife schedule after accept:", e)

            Notification.objects.create(
                user=link_req.linker,
                title="Link Request Accepted",
                message=f"{request.user.get_full_name() or request.user.username} accepted your family link request.",
            )
            messages.success(request, message)
        else:
            messages.error(request, message)

    elif action == 'decline':
        # Keep record but do not link
        link_req.accepted = False
        link_req.save()
        Notification.objects.create(
            user=link_req.linker,
            title="Link Request Declined",
            message=f"{request.user.get_full_name() or request.user.username} declined your family link request.",
        )
        messages.info(request, "Link request declined.")

    else:
        # If no action provided (likely a GET), redirect to dashboard and inform user
        messages.info(request, 'You have a pending family link request. Use the notifications or requests page to respond.')
        return redirect('dashboards:dashboard')

    return redirect('dashboards:dashboard')

def can_edit_pregnancy(user, pregnancy):
    if user.role == "MIDWIFE":
        return True
    if user.role == "DOCTOR":
        return True
    if user.role == "HOSPITAL":
        return True
    if user.role in ["MOTHER", "FATHER"]:
        return True
    return False


@login_required
def end_pregnancy(request, id):
    pregnancy = get_object_or_404(Pregnancy, id=id)

    if not can_edit_pregnancy(request.user, pregnancy):   # your permission function
        messages.error(request, "You do not have permission to end this pregnancy.")
        return redirect('dashboards:dashboard')

    if request.method == "POST":
        form = EndPregnancyForm(request.POST)
        
        if form.is_valid():
            actual_date = form.cleaned_data['actual_delivery_date']
            baby_count = form.cleaned_data.get('baby_count', 1)
            delivery_type = request.POST.get('delivery_type', 'normal')

            # End Pregnancy
            pregnancy.end_pregnancy(actual_date)

            # Create Postpartum Profile for Mother
            PostpartumProfile.objects.create(
                user=pregnancy.mother.user,
                delivery_date=actual_date,
                delivery_type=delivery_type,
                baby_count=baby_count
            )

            # Create Baby Profiles
            babies_created = []
            for i in range(baby_count):
                baby_name = request.POST.get(f'baby_name_{i}', '').strip() or f"Baby {i+1}"
                baby_gender = request.POST.get(f'baby_gender_{i}', 'unknown')
                birth_weight = request.POST.get(f'birth_weight_{i}')

                baby = BabyProfile.objects.create(
                    pregnancy=pregnancy,
                    name=baby_name,
                    gender=baby_gender,
                    birth_date=actual_date,
                    birth_weight_kg=float(birth_weight) if birth_weight else None,
                )
                babies_created.append(baby)

            # Create Postpartum Schedule
            create_postpartum_schedule(pregnancy)

            messages.success(request, f"Pregnancy ended successfully! {len(babies_created)} baby(ies) registered.")
            return redirect('dashboards:midwife_mother_detail', pregnancy.id)

    else:
        form = EndPregnancyForm()

    context = {
        "form": form,
        "pregnancy": pregnancy,
        "mother": pregnancy.mother,
    }
    return render(request, "end_pregnancy.html", context)


@login_required
def add_pregnancy_progress(request, pregnancy_id):
    pregnancy = Pregnancy.objects.get(id=pregnancy_id)

    if not can_edit_pregnancy(request.user, pregnancy):
        return redirect("dashboards:dashboard")

    if request.method == "POST":
        form = PregnancyProgressForm(request.POST)

        if form.is_valid():
            obj = form.save(commit=False)
            obj.pregnancy = pregnancy

           
            obj.recorded_by = request.user
           
            obj.save()
            return redirect("dashboards:dashboard")

    else:
        form = PregnancyProgressForm(initial={"pregnancy": pregnancy})

    return render(request, "progress_form.html", {
        "form": form,
        "pregnancy": pregnancy
    })


#fetal health view
@login_required
def add_fetal_health(request, pregnancy_id):
    pregnancy = Pregnancy.objects.get(id=pregnancy_id)

    if not can_edit_pregnancy(request.user, pregnancy):
        return redirect("dashboards:dashboard")

    if request.method == "POST":
        form = FetalHealthForm(request.POST)

        if form.is_valid():
            obj = form.save(commit=False)
            obj.pregnancy = pregnancy

            
            obj.recorded_by = request.user

            obj.save()
            return redirect("dashboards:dashboard")

    else:
        form = FetalHealthForm()

    return render(request, "fetal_form.html", {"form": form})


#lab test view

@login_required
def add_lab_test(request, pregnancy_id):
    pregnancy = Pregnancy.objects.get(id=pregnancy_id)

    if not can_edit_pregnancy(request.user, pregnancy):
        return redirect("dashboards:dashboard")

    if request.method == "POST":
        form = LabTestForm(request.POST, request.FILES)

        if form.is_valid():
            lab = form.save(commit=False)
            lab.pregnancy = pregnancy
            lab.recorded_by = request.user
            lab.save()

            # IMPORTANT: handle multiple files manually
            files = request.FILES.getlist('attachments')

            for f in files:
                LabAttachment.objects.create(
                    post=lab,
                    file=f
                )

            return redirect("dashboards:dashboard")

    else:
        form = LabTestForm()

    return render(request, "lab_form.html", {"form": form})


# Auto-create default schedule when pregnancy starts
def create_default_pregnancy_schedule(pregnancy):
    """Create important trimester milestones as ScheduleEvents 
    so parents can see exact dates and reschedule them."""
    
    today = timezone.now().date()

    # ====================== IMPORTANT TRIMESTER MILESTONES ======================
    milestones = [
        # First Trimester
        {"title": "Confirm Pregnancy & First Prenatal Visit", 
         "event_type": "midwife_visit", 
         "days_from_now": 14, 
         "notes": "Blood test, confirmation, and initial checkup"},
        
        {"title": "Start Prenatal Vitamins", 
         "event_type": "milestone", 
         "days_from_now": 7, 
         "notes": "Begin Folic acid and prenatal supplements daily"},
        
        {"title": "First Ultrasound (Dating Scan)", 
         "event_type": "ultrasound", 
         "days_from_now": 70,   # ~Week 10
         "notes": "Confirm due date and check baby’s heartbeat"},
        
        # Second Trimester
        {"title": "Anatomy Scan (Level 2 Ultrasound)", 
         "event_type": "ultrasound", 
         "days_from_now": 140,  # ~Week 20
         "notes": "Detailed scan to check baby’s development"},
        
        {"title": "Glucose Screening Test", 
         "event_type": "lab_test", 
         "days_from_now": 182,  # ~Week 26
         "notes": "Test for gestational diabetes"},
        
        # Third Trimester
        {"title": "Group B Strep Test", 
         "event_type": "lab_test", 
         "days_from_now": 245,  # ~Week 35
         "notes": "Important test before delivery"},
        
        {"title": "Birth Plan Discussion & Hospital Tour", 
         "event_type": "hospital_clinic", 
         "days_from_now": 224,  # ~Week 32
         "notes": "Discuss birth preferences and visit hospital"},
        
        {"title": "Final Weeks Preparation", 
         "event_type": "milestone", 
         "days_from_now": 266,  # ~Week 38
         "notes": "Hospital bag ready, final checkups"},
    ]

    for m in milestones:
        scheduled_date = today + timedelta(days=m["days_from_now"])
        
        ScheduleEvent.objects.create(
            pregnancy=pregnancy,
            title=m["title"],
            event_type=m["event_type"],
            scheduled_date=scheduled_date,
            notes=m["notes"],
            what_to_bring="Previous medical records",
            created_by=pregnancy.mother.user,   # Created by mother initially
            location="Clinic / Hospital"
        )

    print(f"✅ Default milestone schedule created for pregnancy {pregnancy.id}")
    

def create_midwife_visits_for_pregnancy(pregnancy, midwife):
    """Create midwife visits when midwife is linked.
    Respects max 10 visits per day per midwife."""
    
    # Remove any old midwife visits for this pregnancy
    ScheduleEvent.objects.filter(
        pregnancy=pregnancy,
        event_type="midwife_visit"
    ).delete()

    today = timezone.now().date()
    visit_count = 0
    current_date = today + timedelta(days=7)  # Start from next week

    while visit_count < 10:  # Create exactly 10 visits
        # Check how many visits this midwife already has on this date
        daily_count = ScheduleEvent.objects.filter(
            event_type="midwife_visit",
            created_by=midwife.user,
            scheduled_date=current_date
        ).count()

        if daily_count < 10:
            ScheduleEvent.objects.create(
                pregnancy=pregnancy,
                title=f"Midwife Visit #{visit_count + 1}",
                event_type="midwife_visit",
                scheduled_date=current_date,
                notes="Routine prenatal checkup",
                what_to_bring="Weight log, urine sample, questions",
                created_by=midwife.user,          # Important: Created by midwife
                location="Mother's Home / Clinic"
            )
            visit_count += 1
            current_date += timedelta(days=28)   # ~every 4 weeks
        else:
            # Skip this day if midwife is full (10 visits)
            current_date += timedelta(days=1)

    print(f"✅ Created {visit_count} midwife visits for pregnancy {pregnancy.id} by {midwife.midwife_id}")


@login_required
def reschedule_event(request, event_id):
    event = ScheduleEvent.objects.get(id=event_id)
    
    if not can_edit_pregnancy(request.user, event.pregnancy):
        messages.error(request, "You don't have permission to reschedule this visit.")
        return redirect("dashboards:dashboard")

    if request.method == "POST":
        form = RescheduleEventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Visit rescheduled successfully!")
            return redirect("dashboards:dashboard")
    else:
        form = RescheduleEventForm(instance=event)

    return render(request, "reschedule_form.html", {
        "form": form,
        "event": event
    })

# === VIEWS ===

@login_required
def add_schedule_event(request, pregnancy_id):
    pregnancy = Pregnancy.objects.get(id=pregnancy_id)
    if not can_edit_pregnancy(request.user, pregnancy):
        return redirect("dashboards:dashboard")

    if request.method == "POST":
        form = ScheduleEventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.pregnancy = pregnancy
            event.created_by = request.user
            event.save()
            messages.success(request, "Schedule event added!")
            return redirect("dashboards:dashboard")
    else:
        form = ScheduleEventForm()

    return render(request, "schedule_form.html", {"form": form, "pregnancy": pregnancy})


@login_required
def complete_event(request, event_id):
    event = ScheduleEvent.objects.get(id=event_id)
    if can_edit_pregnancy(request.user, event.pregnancy):
        event.mark_completed()
        messages.success(request, f"{event.title} marked as completed!")
    return redirect("dashboards:dashboard")


@login_required
def complete_task(request, task_id):
    task = TrimesterTask.objects.get(id=task_id)
    if can_edit_pregnancy(request.user, task.pregnancy):
        task.mark_completed()
    return redirect("dashboards:dashboard")


def update_pregnancy_with_schedule(request, pregnancy):
    """Called when starting pregnancy"""
    create_default_pregnancy_schedule(pregnancy)

@login_required
def babyai(request, id):
    baby = get_object_or_404(BabyProfile, id=id)
    
    # Get recent development records
    records = BabyDevelopmentRecord.objects.filter(baby=baby).order_by('-recorded_at')[:8]
    latest_record = records.first() if records.exists() else None

    ai_summary = None
    ai_response = None
    user_query = None

    if request.method == "POST":
        # Handle user question
        user_query = request.POST.get('query', '').strip()
        if user_query:
            context = prepare_baby_context(baby, records)
            ai_response = get_groq_baby_response(context, user_query, is_summary=False)
    
    else:
        # GET request → Generate automatic summary
        context = prepare_baby_context(baby, records)
        ai_summary = get_groq_baby_response(context, "", is_summary=True)

    return render(request, 'babyai.html', {
        'baby': baby,
        'records': records,
        'latest_record': latest_record,
        'ai_summary': ai_summary,
        'ai_response': ai_response,
        'query': user_query,
    })


def prepare_baby_context(baby, records):
    """Prepare baby data for AI"""
    data = {
        "baby_name": baby.name or "Baby",
        "gender": baby.gender.capitalize(),
        "current_age_weeks": baby.get_age_in_weeks() or "Not born yet",
        "age_display": baby.get_age_display(),
        "birth_weight_kg": baby.birth_weight_kg,
        "birth_height_cm": baby.birth_height_cm,
        "is_alive": baby.is_alive,
        "notes": baby.notes[:300] if baby.notes else None,
        "development_records": []
    }

    for record in records:
        data["development_records"].append({
            "week": record.age_in_weeks,
            "date": record.recorded_at.strftime("%d %b %Y"),
            "weight_kg": record.weight_kg,
            "height_cm": record.height_cm,
            "head_circumference_cm": record.head_circumference_cm,
            "feeding": record.feeding_type,
            "milestones": record.milestones_achieved[:250] if record.milestones_achieved else None,
            "concerns": record.concerns[:250] if record.concerns else None,
        })
    
    return data


def get_groq_baby_response(context, user_query="", is_summary=False):
    """Call Groq API"""
    client = Groq(api_key=settings.GROQ_API_KEY)

    system_prompt = """You are a warm, experienced pediatric nurse and early childhood development expert. 
    Give practical, encouraging, and evidence-based advice. Always remind parents to consult their doctor for medical concerns."""

    if is_summary:
        user_prompt = f"""
Provide a warm, comprehensive summary for the parent about their baby.

Baby Information:
- Name: {context['baby_name']}
- Gender: {context['gender']}
- Age: {context['age_display']}
- Birth Weight: {context['birth_weight_kg']} kg
- Birth Height: {context['birth_height_cm']} cm

Recent Development Records:
{json.dumps(context['development_records'], indent=2)}

Write a friendly, positive, and insightful summary (maximum 280-350 words). 
Highlight growth, milestones, feeding, and gentle recommendations.
"""
    else:
        user_prompt = f"""
Baby Information:
- Name: {context['baby_name']}
- Gender: {context['gender']}
- Age: {context['age_display']}

Recent Records:
{json.dumps(context['development_records'], indent=2)}

Parent's Question: {user_query}

Give a helpful, personalized, and caring response.
"""

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",   # Excellent balance of quality and speed
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=700 if is_summary else 800,
        )
        return completion.choices[0].message.content.strip()

    except Exception as e:
        return f"⚠️ AI service is temporarily unavailable. Please try again later. ({str(e)})"
    