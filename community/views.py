from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import *
from .forms import (
    ForumPostForm, 
    ForumCommentForm, 
    GroupPostForm, 
    GroupCommentForm,
    ForumCommentAnonymousForm,
    ClinicScheduleForm,
    GroupForm,
)
from accounts.models import (
    DoctorProfile,
    HospitalProfile,
    HospitalStaffProfile,
    MidwifeProfile,
    Role,
)
from dashboards.models import ScheduleEvent, Clinics
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date, parse_time
from django.db import transaction
from django.db.models import Q
from .services.personalization import CommunityPersonalizationService

User = get_user_model()


# === HELPER FUNCTIONS ===

def managed_hospital(user):
    hospital = HospitalProfile.objects.filter(user=user).first()
    if hospital:
        return hospital
    staff = HospitalStaffProfile.objects.filter(
        user=user, is_active=True
    ).select_related("hospital").first()
    return staff.hospital if staff else None


def midwife_group_owner(user):
    if getattr(user, "role", None) != Role.MIDWIFE:
        return None
    return MidwifeProfile.objects.filter(user=user).first()


def doctor_group_owner(user):
    if getattr(user, "role", None) != Role.DOCTOR:
        return None
    return DoctorProfile.objects.filter(user=user).first()


def can_create_groups(user):
    return (
        managed_hospital(user) is not None
        or midwife_group_owner(user) is not None
        or doctor_group_owner(user) is not None
    )


def can_manage_group(user, group):
    hospital = managed_hospital(user)
    if hospital and hospital == group.hospital:
        return True
    if group.created_by_id == user.id:
        return True
    return GroupMember.objects.filter(
        group=group,
        user=user,
        role__in=[GroupMember.Role.ADMIN, GroupMember.Role.MIDWIFE],
    ).exists()


def can_use_community_ai(user, group):
    role = getattr(user, "role", None)
    if role not in [Role.DOCTOR, Role.MIDWIFE]:
        return False

    is_professional_member = GroupMember.objects.filter(
        group=group,
        user=user,
        role__in=[GroupMember.Role.DOCTOR, GroupMember.Role.MIDWIFE],
    ).exists()
    if is_professional_member:
        return True

    # Group creators are added as admins, so their professional membership
    # role is not stored on the group member record.
    if role == Role.DOCTOR and group.owner_doctor_id:
        is_owner = group.owner_doctor.user_id == user.id
    elif role == Role.MIDWIFE and group.owner_midwife_id:
        is_owner = group.owner_midwife.user_id == user.id
    else:
        is_owner = False

    return is_owner and GroupMember.objects.filter(
        group=group,
        user=user,
        role=GroupMember.Role.ADMIN,
    ).exists()


def community_post_for_ai(group_id, post_id):
    return get_object_or_404(
        GroupPost.objects.select_related("group", "author"),
        pk=post_id,
        group_id=group_id,
    )


def midwife_linked_hospitals(user):
    """Hospitals in care teams to which this midwife is currently linked."""
    return HospitalProfile.objects.filter(
        hospital_familiy__midwife__user=user,
    ).distinct().order_by("name")


def create_notification(user, notification_type, title, message, forum_post=None, hospital_group=None, clinic_schedule=None):
    """Create a notification for a user"""
    CommunityNotification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        forum_post=forum_post,
        hospital_group=hospital_group,
        clinic_schedule=clinic_schedule
    )


def notify_subscribers(forum_post, notification_type='new_post'):
    """Notify all subscribers of a forum about new posts"""
    category = forum_post.category
    subscribers = ForumSubscription.objects.filter(forum=category).select_related('user')
    
    for subscription in subscribers:
        create_notification(
            user=subscription.user,
            notification_type=notification_type,
            title=f"New Post: {forum_post.title}",
            message=f"A new post has been added to {category.name}",
            forum_post=forum_post
        )


def notify_hospital_group_subscribers(group_post, group):
    """Notify all subscribers of a hospital group about new posts"""
    subscribers = HospitalGroupSubscription.objects.filter(
        hospital_group=group,
        notify_new_posts=True
    ).select_related('user')
    
    for subscription in subscribers:
        create_notification(
            user=subscription.user,
            notification_type='new_post',
            title=f"New Update: {group.name}",
            message=f"New post in {group.name}",
            hospital_group=group
        )


def notify_clinic_schedule(clinic_schedule):
    """Notify hospital group members about new clinic schedule"""
    hospital = clinic_schedule.hospital
    group = HospitalGroup.objects.filter(hospital=hospital).first()
    
    if group:
        members = GroupMember.objects.filter(group=group).select_related('user')
        subscribers = HospitalGroupSubscription.objects.filter(
            hospital_group=group,
            notify_clinic_schedule=True
        ).select_related('user')
        
        # Notify all subscribers
        for subscription in subscribers:
            create_notification(
                user=subscription.user,
                notification_type='clinic_schedule',
                title=f"New Clinic Schedule: {clinic_schedule.title}",
                message=f"{hospital.name} has scheduled a new clinic: {clinic_schedule.title}",
                clinic_schedule=clinic_schedule
            )


def notify_clinic_patients(clinic, title, message):
        """Notify booked patients and opted-in hospital group subscribers."""
        patient_ids = set(
            ScheduleEvent.objects.filter(clinic=clinic).values_list(
                'pregnancy__mother__user_id', flat=True
            )
        )
        recipient_groups = {user_id: None for user_id in patient_ids}

        subscriptions = HospitalGroupSubscription.objects.filter(
            hospital_group__hospital=clinic.hospital,
            notify_announcements=True,
        ).select_related('hospital_group')
        for subscription in subscriptions:
            recipient_groups[subscription.user_id] = subscription.hospital_group

        users = User.objects.in_bulk(recipient_groups)
        for user_id, group in recipient_groups.items():
            user = users.get(user_id)
            if user:
                create_notification(
                    user=user,
                    notification_type='hospital_announcement',
                    title=title,
                    message=message,
                    hospital_group=group,
                )


@login_required
def hospital_staff_dashboard(request):
        """Dashboard for hospital staff to manage clinics, patients and groups."""
        hospital = managed_hospital(request.user)
        if not hospital:
            messages.error(request, 'You must be hospital staff to access this dashboard.')
            return redirect('community:group_list')

        clinics = Clinics.objects.filter(hospital=hospital).order_by('date')
        groups = HospitalGroup.objects.filter(hospital=hospital)

        # Upcoming appointments for hospital clinics
        upcoming_appointments = ScheduleEvent.objects.filter(
            clinic__hospital=hospital,
            scheduled_date__gte=timezone.now().date()
        ).select_related('pregnancy__mother__user').order_by('scheduled_date')[:100]

        # Forms for quick actions
        group_form = GroupForm()
        clinic_form = None
        post_form = GroupPostForm()

        return render(request, 'hospital_dashboard.html', {
            'hospital': hospital,
            'clinics': clinics,
            'groups': groups,
            'upcoming_appointments': upcoming_appointments,
            'group_form': group_form,
            'clinic_form': clinic_form,
            'post_form': post_form,
        })


@login_required
@require_POST
def create_clinic_announcement(request, clinic_id):
        """Create an announcement for a clinic and notify patients and group subscribers."""
        clinic = get_object_or_404(Clinics, pk=clinic_id)
        hospital = clinic.hospital
        if managed_hospital(request.user) != hospital:
            return HttpResponseForbidden("You cannot manage this clinic.")

        title = request.POST.get('title') or f"Announcement: {clinic.name}"
        message = (request.POST.get('message') or '').strip()
        if not message:
            messages.error(request, 'Enter an announcement message.')
            return redirect('community:hospital_dashboard')

        # Notify patients booked for this clinic and subscribers
        notify_clinic_patients(clinic, title, message)

        messages.success(request, 'Announcement sent to clinic patients and subscribers.')
        return redirect('community:hospital_dashboard')


@login_required
@require_POST
def create_group_and_add_members(request):
        """Create a hospital group and optionally add members (by username list)."""
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            hospital = managed_hospital(request.user)
            if not hospital:
                return HttpResponseForbidden("You cannot create a hospital group.")
            group.hospital = hospital
            group.created_by = request.user
            group.save()
            GroupMember.objects.get_or_create(
                group=group,
                user=request.user,
                defaults={"role": GroupMember.Role.ADMIN},
            )

            # Add members by comma-separated usernames
            members = request.POST.get('members', '')
            for username in [u.strip() for u in members.split(',') if u.strip()]:
                try:
                    user = User.objects.get(username=username)
                    GroupMember.objects.get_or_create(group=group, user=user, defaults={'role': 'PATIENT'})
                except User.DoesNotExist:
                    continue

            messages.success(request, 'Group created and members added.')
        else:
            messages.error(request, 'Invalid group data.')

        return redirect('community:hospital_dashboard')


@login_required
@require_POST
def reschedule_appointment(request, appointment_id):
        """Reschedule a ScheduleEvent (appointment). Expects POST with `date` and optional `time`."""
        appt = get_object_or_404(ScheduleEvent, pk=appointment_id)
        hospital = managed_hospital(request.user)
        if not hospital or appt.clinic_id is None or appt.clinic.hospital_id != hospital.id:
            return HttpResponseForbidden("You cannot manage this appointment.")

        date = parse_date(request.POST.get('date', ''))
        time_value = request.POST.get('time', '')
        time = parse_time(time_value) if time_value else None
        clinic_id = request.POST.get('clinic_id')
        if not date:
            return JsonResponse({'error': 'A valid date is required.'}, status=400)
        if time_value and not time:
            return JsonResponse({'error': 'Enter a valid time.'}, status=400)
        appt.scheduled_date = date
        appt.scheduled_time = time
        if clinic_id:
            try:
                appt.clinic = Clinics.objects.get(pk=clinic_id, hospital=hospital)
            except Clinics.DoesNotExist:
                return JsonResponse({'error': 'Clinic not found.'}, status=400)
        appt.save()

        # Notify patient about reschedule
        try:
            user = appt.pregnancy.mother.user
            create_notification(user=user, notification_type='clinic_schedule', title='Appointment Rescheduled', message=f'Your appointment "{appt.title}" was rescheduled to {appt.scheduled_date} {appt.scheduled_time or ""}')
        except Exception:
            pass

        messages.success(request, 'Appointment rescheduled and patient notified.')
        return redirect('community:hospital_dashboard')


# --- Forum Section ---
def forum_home(request):
    posts = ForumPost.objects.all().order_by('-created_at')
    categories = ForumCategory.objects.all()
    
    # Check if user is authenticated for subscription features
    user_subscribed_forums = []
    if request.user.is_authenticated:
        user_subscribed_forums = ForumSubscription.objects.filter(user=request.user).values_list('forum_id', flat=True)
    
    return render(request, 'forum_list.html', {
        'posts': posts, 
        'categories': categories,
        'user_subscribed_forums': user_subscribed_forums
    })


def post_detail(request, pk):
    post = get_object_or_404(ForumPost, pk=pk)
    # Using parent=None allows for threaded comment logic later
    comments = post.comments.filter(parent=None).order_by('-created_at')
    anonymous_comments = post.anonymous_comments.all().order_by('-created_at')
    
    if request.method == 'POST':
        if request.user.is_authenticated:
            form = ForumCommentForm(request.POST)
            if form.is_valid():
                comment = form.save(commit=False)
                comment.post = post
                comment.author = request.user
                comment.save()
                
                # Notify post author
                if post.author != request.user:
                    create_notification(
                        user=post.author,
                        notification_type='new_comment',
                        title=f"New Comment on '{post.title}'",
                        message=f"{request.user.get_full_name() or request.user.username} commented on your post",
                        forum_post=post
                    )
                
                messages.success(request, 'Comment posted successfully!')
                return redirect('community:post_detail', pk=post.pk)
        else:
            # Anonymous comment
            form = ForumCommentAnonymousForm(request.POST)
            if form.is_valid():
                comment = form.save(commit=False)
                comment.post = post
                comment.save()
                
                # Notify post author about anonymous comment
                create_notification(
                    user=post.author,
                    notification_type='new_comment',
                    title=f"New Comment on '{post.title}'",
                    message=f"An anonymous comment was added to your post",
                    forum_post=post
                )
                
                messages.success(request, 'Your comment has been posted anonymously!')
                return redirect('community:post_detail', pk=post.pk)
    else:
        form = ForumCommentForm() if request.user.is_authenticated else ForumCommentAnonymousForm()

    return render(request, 'post_detail.html', {
        'post': post, 
        'comments': comments,
        'anonymous_comments': anonymous_comments,
        'form': form,
        'is_authenticated': request.user.is_authenticated
    })


@login_required
def create_group(request):
    """Hospital teams and midwives create custom community groups."""
    hospital = managed_hospital(request.user)
    midwife = midwife_group_owner(request.user)
    doctor = doctor_group_owner(request.user)
    if not hospital and not midwife and not doctor:
        messages.error(request, 'Only hospital teams, doctors, and registered midwives can create groups.')
        return redirect('community:group_list')

    linked_hospitals = midwife_linked_hospitals(request.user) if midwife else HospitalProfile.objects.none()
    
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            if hospital:
                group.hospital = hospital
            elif midwife:
                selected_hospital_id = request.POST.get("hospital_id", "").strip()
                selected_hospital = (
                    linked_hospitals.filter(id=selected_hospital_id).first()
                    if selected_hospital_id
                    else None
                )
                if selected_hospital_id and not selected_hospital:
                    form.add_error(None, "Select a hospital linked to your care teams.")
                    return render(request, 'group_create.html', {
                        'form': form,
                        'hospital': None,
                        'owner_label': f"Midwife {request.user.get_full_name() or request.user.username}",
                        'available_hospitals': linked_hospitals,
                        'is_midwife_owner': True,
                    }, status=400)
                group.hospital = selected_hospital
                group.owner_midwife = midwife
            else:
                group.owner_doctor = doctor
                group.hospital = doctor.hospital
            # Hospital communities are invitation-only; membership is the
            # access boundary for both the directory and its discussions.
            if group.hospital_id:
                group.is_private = True
            group.created_by = request.user
            group.save()
            GroupMember.objects.get_or_create(
                group=group,
                user=request.user,
                defaults={"role": GroupMember.Role.ADMIN},
            )
            
            messages.success(request, f'Group "{group.name}" created successfully!')
            return redirect('community:group_detail', pk=group.id)
    else:
        form = GroupForm()
    
    return render(request, 'group_create.html', {
        'form': form,
        'hospital': hospital,
        'owner_label': (
            hospital.name
            if hospital
            else (
                f"Midwife {request.user.get_full_name() or request.user.username}"
                if midwife
                else f"Dr. {request.user.get_full_name() or request.user.username}"
            )
        ),
        'available_hospitals': linked_hospitals,
        'is_midwife_owner': midwife is not None,
        'is_doctor_owner': doctor is not None,
    })


@login_required
def create_post(request):
    """Allow signed-in users to post with their identity hidden when requested."""
    if request.method == 'POST':
        form = ForumPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            
            post.author = request.user
            
            post.save()
            
            # Use 'attachments' to match your MultipleFileField in forms.py
            files = request.FILES.getlist('attachments')
            for f in files:
                ForumAttachment.objects.create(post=post, file=f)
            
            # Notify forum subscribers
            notify_subscribers(post)
            
            messages.success(request, 'Post published successfully!')
            return redirect('community:post_detail', pk=post.pk)
    else:
        form = ForumPostForm()
    
    return render(request, 'post_forum.html', {'form': form})


@login_required
@require_POST
def subscribe_forum(request, forum_id):
    """Subscribe user to forum notifications"""
    forum = get_object_or_404(ForumCategory, pk=forum_id)
    ForumSubscription.objects.get_or_create(user=request.user, forum=forum)
    messages.success(request, f'You are now subscribed to {forum.name}!')
    return redirect('community:forum_home')


@login_required
@require_POST
def unsubscribe_forum(request, forum_id):
    """Unsubscribe user from forum notifications"""
    forum = get_object_or_404(ForumCategory, pk=forum_id)
    ForumSubscription.objects.filter(user=request.user, forum=forum).delete()
    messages.success(request, f'You have unsubscribed from {forum.name}.')
    return redirect('community:forum_home')


# --- Hospital Group Section ---
@login_required
def group_list(request):
    member_group_ids = GroupMember.objects.filter(
        user=request.user
    ).values_list('group_id', flat=True)
    managed_group_ids = [
        group.id for group in HospitalGroup.objects.all()
        if can_manage_group(request.user, group)
    ]
    groups = HospitalGroup.objects.filter(
        Q(is_private=False, hospital__isnull=True) |
        Q(id__in=member_group_ids) |
        Q(id__in=managed_group_ids)
    ).distinct()
    
    # Get subscriptions for authenticated users
    user_subscriptions = {}
    if request.user.is_authenticated:
        user_subscriptions = {
            sub.hospital_group_id: sub 
            for sub in HospitalGroupSubscription.objects.filter(user=request.user)
        }
    
    return render(request, 'group_list.html', {
        'groups': groups,
        'user_subscriptions': user_subscriptions,
        'can_manage_groups': can_create_groups(request.user),
        'user_group_ids': set(
            GroupMember.objects.filter(user=request.user).values_list('group_id', flat=True)
        ),
    })


@login_required
def group_detail(request, pk):
    group = get_object_or_404(HospitalGroup, pk=pk)
    user_can_manage_group = can_manage_group(request.user, group)
    is_member = (
        user_can_manage_group
        or GroupMember.objects.filter(group=group, user=request.user).exists()
    )
    
    if (group.is_private or group.hospital_id) and not is_member:
        messages.error(request, 'You do not have access to this private group.')
        return redirect('community:group_list')
    
    posts = list(
        group.posts.prefetch_related(
            'comments__author',
            'attachments',
            'ai_insights',
        ).all().order_by('-created_at')
    )
    for post in posts:
        latest_by_kind = {}
        for insight in post.ai_insights.all():
            latest_by_kind.setdefault(insight.kind, insight)
        post.latest_ai_insights = list(latest_by_kind.values())
        post.visible_comments = [
            comment for comment in post.comments.all()
            if (
                not comment.is_private
                or comment.author_id == request.user.id
                or comment.recipient_id == request.user.id
                or user_can_manage_group
            )
        ]
    clinic_schedules = (
        group.hospital.clinic_schedules.filter(
            scheduled_date__gte=timezone.now().date()
        ).order_by('scheduled_date')[:10]
        if group.hospital_id
        else ClinicSchedule.objects.none()
    )
    
    # Get subscription info
    subscription = None
    if request.user.is_authenticated:
        subscription = HospitalGroupSubscription.objects.filter(
            user=request.user,
            hospital_group=group
        ).first()
    
    # Handle Group Posting
    if request.method == 'POST' and is_member:
        form = GroupPostForm(request.POST, request.FILES)
        if form.is_valid():
            g_post = form.save(commit=False)
            g_post.group = group
            g_post.author = request.user
            g_post.save()
            
            # Handle Group Attachments
            files = request.FILES.getlist('attachments')
            for f in files:
                GroupAttachment.objects.create(post=g_post, file=f)
            
            # Notify subscribers
            notify_hospital_group_subscribers(g_post, group)
            
            messages.success(request, 'Post published successfully!')
            return redirect('community:group_detail', pk=group.pk)
    else:
        form = GroupPostForm()

    return render(request, 'group_detail.html', {
        'group': group, 
        'posts': posts,
        'posts_count': len(posts),
        'clinic_schedules': clinic_schedules,
        'is_member': is_member,
        'form': form,
        'subscription': subscription,
        'can_manage_group': user_can_manage_group,
        'can_use_community_ai': can_use_community_ai(request.user, group),
    })


@login_required
@require_POST
def add_group_comment(request, group_id, post_id):
    post = community_post_for_ai(group_id, post_id)
    if not GroupMember.objects.filter(group=post.group, user=request.user).exists():
        return HttpResponseForbidden("You must belong to this community to respond.")
    content = request.POST.get("content", "").strip()
    is_private = request.POST.get("visibility") == "private"
    recipient = post.author if is_private else None
    if is_private and (
        not can_use_community_ai(request.user, post.group)
        or post.author_id == request.user.id
    ):
        return HttpResponseForbidden("Only a doctor or midwife can send a private response to the mother.")
    if not content:
        messages.error(request, "Enter a response before posting.")
    else:
        GroupComment.objects.create(
            post=post,
            author=request.user,
            content=content,
            is_private=is_private,
            recipient=recipient,
        )
        if is_private and post.author_id != request.user.id:
            create_notification(
                user=post.author,
                notification_type="new_comment",
                title="Private response from your care team",
                message=f"{request.user.get_full_name() or request.user.username} sent you a private response.",
                hospital_group=post.group,
            )
        messages.success(request, "Response posted.")
    return redirect("community:group_detail", pk=post.group_id)


def _require_community_ai_access(request, group):
    if not can_use_community_ai(request.user, group):
        return HttpResponseForbidden(
            "Only an authorized doctor or midwife in this community can use AI support."
        )
    return None


def _require_mother_member(post):
    if post.author.role != Role.MOTHER:
        return HttpResponseForbidden("AI community support is available only for mothers.")
    if not GroupMember.objects.filter(
        group=post.group,
        user=post.author,
        role=GroupMember.Role.PATIENT,
    ).exists():
        return HttpResponseForbidden(
            "This mother is not an authorized member of this community."
        )
    return None


@login_required
@require_POST
def request_mother_summary(request, group_id, post_id):
    post = community_post_for_ai(group_id, post_id)
    denied = _require_community_ai_access(request, post.group)
    if denied:
        return denied
    denied = _require_mother_member(post)
    if denied:
        return denied
    mother = getattr(post.author, "user_mother", None)
    if not mother:
        messages.error(request, "AI summaries are available only for mother-authored concerns.")
        return redirect("community:group_detail", pk=post.group_id)
    context = CommunityPersonalizationService().build_context(
        mother,
        post.content,
        triggered_by=request.user,
        viewer_role=request.user.role,
    )
    insight = CommunityAIInsight.objects.create(
        group_post=post,
        requested_by=request.user,
        kind=CommunityAIInsight.Kind.SUMMARY,
        content=CommunityPersonalizationService().generate_summary(context),
    )
    messages.success(request, "Mother current-status summary generated for professional review.")
    return redirect("community:group_detail", pk=post.group_id)


@login_required
@require_POST
def personalize_group_response(request, group_id, post_id):
    post = community_post_for_ai(group_id, post_id)
    denied = _require_community_ai_access(request, post.group)
    if denied:
        return denied
    denied = _require_mother_member(post)
    if denied:
        return denied
    professional_response = request.POST.get("response", "").strip()
    if not professional_response:
        messages.error(request, "Write the professional response before requesting personalization.")
        return redirect("community:group_detail", pk=post.group_id)
    mother = getattr(post.author, "user_mother", None)
    if not mother:
        messages.error(request, "AI personalization is available only for mother-authored concerns.")
        return redirect("community:group_detail", pk=post.group_id)
    service = CommunityPersonalizationService()
    insight = CommunityAIInsight.objects.create(
        group_post=post,
        requested_by=request.user,
        kind=CommunityAIInsight.Kind.PERSONALIZED_RESPONSE,
        source_response=professional_response,
        content=service.personalize_response(
            service.build_context(
                mother,
                post.content,
                triggered_by=request.user,
                viewer_role=request.user.role,
            ),
            professional_response,
        ),
    )
    messages.success(request, "Personalized draft generated. Review and approve it before posting.")
    return redirect("community:group_detail", pk=post.group_id)


@login_required
@require_POST
def approve_personalized_response(request, group_id, post_id, insight_id):
    post = community_post_for_ai(group_id, post_id)
    denied = _require_community_ai_access(request, post.group)
    if denied:
        return denied
    with transaction.atomic():
        professional_member_ids = GroupMember.objects.filter(
            group=post.group,
            role__in=[GroupMember.Role.DOCTOR, GroupMember.Role.MIDWIFE],
        ).values("user_id")
        owner_user_ids = [
            owner_user_id
            for owner_user_id in (
                getattr(post.group.owner_doctor, "user_id", None),
                getattr(post.group.owner_midwife, "user_id", None),
            )
            if owner_user_id is not None
        ]
        insight = get_object_or_404(
            CommunityAIInsight.objects.filter(
                Q(requested_by__in=professional_member_ids)
                | Q(requested_by_id__in=owner_user_ids)
            ),
            pk=insight_id,
            group_post=post,
            kind=CommunityAIInsight.Kind.PERSONALIZED_RESPONSE,
        )
        if insight.is_approved:
            messages.info(request, "This response has already been approved.")
        else:
            approved_content = request.POST.get("approved_content", "").strip()
            if not approved_content:
                messages.error(request, "Review and edit the response before approving it.")
                return redirect("community:group_detail", pk=post.group_id)
            is_private = request.POST.get("visibility") == "private"
            GroupComment.objects.create(
                post=post,
                author=request.user,
                content=approved_content,
                is_private=is_private,
                recipient=post.author if is_private else None,
            )
            insight.is_approved = True
            insight.approved_by = request.user
            insight.approved_at = timezone.now()
            insight.save(update_fields=["is_approved", "approved_by", "approved_at"])
            create_notification(
                user=post.author,
                notification_type="new_comment",
                title=f"Response to '{post.content[:50]}'",
                message=(
                    "A healthcare professional sent you a private response."
                    if is_private
                    else "A healthcare professional responded to your community concern."
                ),
                hospital_group=post.group,
            )
            messages.success(request, "Personalized response approved and posted.")
    return redirect("community:group_detail", pk=post.group_id)


@login_required
@require_POST
def join_group(request, pk):
    group = get_object_or_404(HospitalGroup, pk=pk)
    if group.is_private or group.hospital_id:
        return HttpResponseForbidden("This group is private and requires an invitation.")
    # Default role set to PATIENT as per your model requirements
    member, created = GroupMember.objects.get_or_create(
        group=group, 
        user=request.user, 
        defaults={
            'role': (
                GroupMember.Role.ADMIN
                if can_manage_group(request.user, group)
                else GroupMember.Role.PATIENT
            )
        }
    )
    
    # Auto-subscribe to hospital group
    HospitalGroupSubscription.objects.get_or_create(user=request.user, hospital_group=group)
    
    if created:
        messages.success(request, f'You have joined {group.name}!')
    else:
        messages.info(request, f'You are already a member of {group.name}.')
    
    return redirect('community:group_detail', pk=pk)


@login_required
@require_POST
def subscribe_group(request, group_id):
    """Subscribe to hospital group notifications"""
    group = get_object_or_404(HospitalGroup, pk=group_id)
    if not GroupMember.objects.filter(group=group, user=request.user).exists():
        return HttpResponseForbidden("You must be a member of this private community.")
    subscription, created = HospitalGroupSubscription.objects.get_or_create(
        user=request.user,
        hospital_group=group
    )
    
    if created:
        messages.success(request, f'You are now subscribed to {group.name} updates!')
    else:
        messages.info(request, f'You are already subscribed to {group.name}.')
    
    return redirect('community:group_detail', pk=group_id)


@login_required
@require_POST
def unsubscribe_group(request, group_id):
    """Unsubscribe from hospital group notifications"""
    group = get_object_or_404(HospitalGroup, pk=group_id)
    HospitalGroupSubscription.objects.filter(user=request.user, hospital_group=group).delete()
    messages.success(request, f'You have unsubscribed from {group.name}.')
    return redirect('community:group_detail', pk=group_id)


# --- Clinic Schedule Section ---
@login_required
def clinic_schedules(request, group_id):
    """View clinic schedules for a hospital group"""
    group = get_object_or_404(HospitalGroup, pk=group_id)
    
    # Check if user is authorized to view (member of group or hospital staff)
    is_member = (
        can_manage_group(request.user, group)
        or GroupMember.objects.filter(group=group, user=request.user).exists()
    )
    if (group.is_private or group.hospital_id) and not is_member:
        messages.error(request, 'You do not have access to this content.')
        return redirect('community:group_list')
    
    schedules = (
        group.hospital.clinic_schedules.filter(
            scheduled_date__gte=timezone.now().date()
        ).order_by('scheduled_date')
        if group.hospital_id
        else ClinicSchedule.objects.none()
    )
    
    return render(request, 'clinic_schedules.html', {
        'group': group,
        'schedules': schedules,
        'is_member': is_member,
        'can_manage_group': can_manage_group(request.user, group),
    })


@login_required
def create_clinic_schedule(request, group_id):
    """Hospital staff create clinic schedules"""
    group = get_object_or_404(HospitalGroup, pk=group_id)
    
    if not group.hospital_id:
        messages.error(request, 'Independent midwife groups do not have hospital clinic schedules.')
        return redirect('community:group_detail', pk=group_id)

    if not can_manage_group(request.user, group):
        messages.error(request, 'You are not authorized to create schedules.')
        return redirect('community:group_detail', pk=group_id)
    
    if request.method == 'POST':
        form = ClinicScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.hospital = group.hospital
            schedule.created_by = request.user
            schedule.available_slots = schedule.max_patients
            schedule.save()
            
            # Notify group members
            notify_clinic_schedule(schedule)
            
            messages.success(request, 'Clinic schedule created successfully!')
            return redirect('community:clinic_schedules', group_id=group_id)
    else:
        form = ClinicScheduleForm()
    
    return render(request, 'create_clinic_schedule.html', {
        'form': form,
        'group': group
    })


@login_required
def manage_group(request, group_id):
    group = get_object_or_404(HospitalGroup, pk=group_id)
    if not can_manage_group(request.user, group):
        return HttpResponseForbidden("You cannot manage this group.")

    form = GroupForm(instance=group)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_group':
            form = GroupForm(request.POST, instance=group)
            if form.is_valid():
                updated_group = form.save(commit=False)
                if updated_group.hospital_id:
                    updated_group.is_private = True
                updated_group.save()
                messages.success(request, 'Group details updated.')
                return redirect('community:manage_group', group_id=group.id)
        elif action == 'add_member':
            identifier = request.POST.get('username', '').strip()
            role = request.POST.get('role', GroupMember.Role.PATIENT)
            if role not in GroupMember.Role.values:
                messages.error(request, 'Select a valid member role.')
            else:
                user = User.objects.filter(username__iexact=identifier).first()
                if not user:
                    messages.error(request, 'No user was found with that username.')
                else:
                    member, created = GroupMember.objects.get_or_create(
                        group=group,
                        user=user,
                        defaults={'role': role},
                    )
                    if not created and member.role != role:
                        member.role = role
                        member.save(update_fields=['role'])
                    HospitalGroupSubscription.objects.get_or_create(
                        user=user,
                        hospital_group=group,
                    )
                    messages.success(request, f'{user.username} is now a group member.')
                    return redirect('community:manage_group', group_id=group.id)

    return render(request, 'group_manage.html', {
        'group': group,
        'form': form,
        'members': group.members.select_related('user').order_by('role', 'user__username'),
        'role_choices': GroupMember.Role.choices,
    })


@login_required
@require_POST
def remove_group_member(request, group_id, member_id):
    group = get_object_or_404(HospitalGroup, pk=group_id)
    if not can_manage_group(request.user, group):
        return HttpResponseForbidden("You cannot manage this group.")
    member = get_object_or_404(GroupMember, pk=member_id, group=group)
    if member.user_id == group.created_by_id:
        messages.error(request, 'The group creator cannot be removed.')
    else:
        username = member.user.username
        HospitalGroupSubscription.objects.filter(
            user=member.user,
            hospital_group=group,
        ).delete()
        member.delete()
        messages.success(request, f'{username} was removed from the group.')
    return redirect('community:manage_group', group_id=group.id)


@login_required
def view_notifications(request):
    """View user's community notifications"""
    notifications = CommunityNotification.objects.filter(user=request.user).select_related(
        'forum_post',
        'hospital_group',
        'clinic_schedule__hospital',
    ).order_by('-created_at')
    for notification in notifications:
        notification.target_group = None
        if notification.clinic_schedule_id:
            notification.target_group = HospitalGroup.objects.filter(
                hospital=notification.clinic_schedule.hospital
            ).first()
    
    if request.method == 'POST':
        # Mark all as read
        notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, 'All notifications marked as read.')
        return redirect('community:view_notifications')
    
    return render(request, 'community_notifications.html', {
        'notifications': notifications,
        'unread_count': notifications.filter(is_read=False).count()
    })
