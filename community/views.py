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
from accounts.models import HospitalProfile, HospitalStaffProfile, MidwifeProfile, Role
from dashboards.models import ScheduleEvent, Clinics
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date, parse_time

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


def can_create_groups(user):
    return managed_hospital(user) is not None or midwife_group_owner(user) is not None


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
    if not hospital and not midwife:
        messages.error(request, 'Only hospital teams and registered midwives can create groups.')
        return redirect('community:group_list')

    linked_hospitals = midwife_linked_hospitals(request.user) if midwife else HospitalProfile.objects.none()
    
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            if hospital:
                group.hospital = hospital
            else:
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
        'owner_label': hospital.name if hospital else f"Midwife {request.user.get_full_name() or request.user.username}",
        'available_hospitals': linked_hospitals,
        'is_midwife_owner': midwife is not None,
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
    groups = HospitalGroup.objects.all()
    
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
    
    if group.is_private and not is_member:
        messages.error(request, 'You do not have access to this private group.')
        return redirect('community:group_list')
    
    posts = group.posts.all().order_by('-created_at')
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
        'clinic_schedules': clinic_schedules,
        'is_member': is_member,
        'form': form,
        'subscription': subscription,
        'can_manage_group': user_can_manage_group,
    })


@login_required
@require_POST
def join_group(request, pk):
    group = get_object_or_404(HospitalGroup, pk=pk)
    if group.is_private and not can_manage_group(request.user, group):
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
    if group.is_private and not is_member:
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
                form.save()
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
