from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
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
from accounts.models import HospitalProfile, MotherProfile
from dashboards.models import ScheduleEvent, Clinics
from django.urls import reverse
from django.http import JsonResponse
from django.contrib.auth import get_user_model

User = get_user_model()


# === HELPER FUNCTIONS ===

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


def notify_clinic_patients(clinic_schedule, title, message):
        """Notify all patients who have appointments in the given clinic (ScheduleEvent).
        Also notify hospital group subscribers via existing helper.
        """
        # Notify patients with appointments in this clinic
        appointments = ScheduleEvent.objects.filter(clinic=clinic_schedule)
        users = set()
        for appt in appointments.select_related('pregnancy__mother__user'):
            try:
                user = appt.pregnancy.mother.user
                users.add(user)
            except Exception:
                continue

        for user in users:
            create_notification(
                user=user,
                notification_type='clinic_schedule',
                title=title,
                message=message,
                clinic_schedule=clinic_schedule
            )

        # Also notify hospital group subscribers
        group = HospitalGroup.objects.filter(hospital=clinic_schedule.hospital).first()
        if group:
            notify_hospital_group_subscribers(None, group)


@login_required
def hospital_staff_dashboard(request):
        """Dashboard for hospital staff to manage clinics, patients and groups."""
        hospital = HospitalProfile.objects.filter(user=request.user).first()
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
def create_clinic_announcement(request, clinic_id):
        """Create an announcement for a clinic and notify patients and group subscribers."""
        clinic = get_object_or_404(Clinics, pk=clinic_id)
        hospital = clinic.hospital

        title = request.POST.get('title') or f"Announcement: {clinic.name}"
        message = request.POST.get('message') or ''

        # Notify patients booked for this clinic and subscribers
        notify_clinic_patients(clinic, title, message)

        messages.success(request, 'Announcement sent to clinic patients and subscribers.')
        return redirect(request.META.get('HTTP_REFERER', reverse('community:group_list')))


@login_required
def create_group_and_add_members(request):
        """Create a hospital group and optionally add members (by username list)."""
        if request.method != 'POST':
            return redirect('community:group_list')

        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            hospital = HospitalProfile.objects.filter(user=request.user).first()
            group.hospital = hospital
            group.created_by = request.user
            group.save()

            # Add members by comma-separated usernames
            members = request.POST.get('members', '')
            for username in [u.strip() for u in members.split(',') if u.strip()]:
                try:
                    user = User.objects.get(username=username)
                    GroupMember.objects.get_or_create(group=group, user=user, defaults={'role': 'PATIENT'})
                except Exception:
                    continue

            messages.success(request, 'Group created and members added.')
        else:
            messages.error(request, 'Invalid group data.')

        return redirect(request.META.get('HTTP_REFERER', reverse('community:group_list')))


@login_required
def reschedule_appointment(request, appointment_id):
        """Reschedule a ScheduleEvent (appointment). Expects POST with `date` and optional `time`."""
        appt = get_object_or_404(ScheduleEvent, pk=appointment_id)
        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid method'}, status=400)

        date = request.POST.get('date')
        time = request.POST.get('time')
        clinic_id = request.POST.get('clinic_id')
        if date:
            appt.scheduled_date = date
        if time:
            appt.scheduled_time = time
        if clinic_id:
            try:
                appt.clinic = Clinics.objects.get(pk=clinic_id)
            except Clinics.DoesNotExist:
                pass
        appt.save()

        # Notify patient about reschedule
        try:
            user = appt.pregnancy.mother.user
            create_notification(user=user, notification_type='clinic_schedule', title='Appointment Rescheduled', message=f'Your appointment "{appt.title}" was rescheduled to {appt.scheduled_date} {appt.scheduled_time or ""}')
        except Exception:
            pass

        messages.success(request, 'Appointment rescheduled and patient notified.')
        return redirect(request.META.get('HTTP_REFERER', reverse('community:group_list')))


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
    """Hospital staff create custom groups"""
    # Check if user is hospital staff
    hospital = HospitalProfile.objects.filter(user=request.user).first()
    
    if not hospital:
        messages.error(request, 'You must be a hospital staff member to create groups.')
        return redirect('community:group_list')
    
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.hospital = hospital
            group.created_by = request.user
            group.save()
            
            messages.success(request, f'Group "{group.name}" created successfully!')
            return redirect('community:group_detail', pk=group.id)
    else:
        form = GroupForm()
    
    return render(request, 'group_create.html', {
        'form': form,
        'hospital': hospital
    })


def create_post(request):
    """Allow anyone (authenticated or anonymous) to create forum posts"""
    if request.method == 'POST':
        form = ForumPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            
            # Only set author if user is authenticated
            if request.user.is_authenticated:
                post.author = request.user
            else:
                # For anonymous posts, create a flag
                post.is_anonymous = True
                # Create an anonymous user if needed (optional - can skip author)
                post.author = request.user if request.user.is_authenticated else None
            
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
def subscribe_forum(request, forum_id):
    """Subscribe user to forum notifications"""
    forum = get_object_or_404(ForumCategory, pk=forum_id)
    ForumSubscription.objects.get_or_create(user=request.user, forum=forum)
    messages.success(request, f'You are now subscribed to {forum.name}!')
    return redirect('community:post_detail') if 'next' not in request.GET else redirect(request.GET.get('next'))


@login_required
def unsubscribe_forum(request, forum_id):
    """Unsubscribe user from forum notifications"""
    forum = get_object_or_404(ForumCategory, pk=forum_id)
    ForumSubscription.objects.filter(user=request.user, forum=forum).delete()
    messages.success(request, f'You have unsubscribed from {forum.name}.')
    return redirect('community:post_detail') if 'next' not in request.GET else redirect(request.GET.get('next'))


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
        'user_subscriptions': user_subscriptions
    })


@login_required
def group_detail(request, pk):
    group = get_object_or_404(HospitalGroup, pk=pk)
    is_member = GroupMember.objects.filter(group=group, user=request.user).exists()
    
    if group.is_private and not is_member:
        return render(request, 'denied.html', {'group': group})
    
    posts = group.posts.all().order_by('-created_at')
    clinic_schedules = group.hospital.clinic_schedules.filter(
        scheduled_date__gte=timezone.now().date()
    ).order_by('scheduled_date')[:10]
    
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
        'subscription': subscription
    })


@login_required
def join_group(request, pk):
    group = get_object_or_404(HospitalGroup, pk=pk)
    # Default role set to PATIENT as per your model requirements
    member, created = GroupMember.objects.get_or_create(
        group=group, 
        user=request.user, 
        defaults={'role': 'PATIENT'}
    )
    
    # Auto-subscribe to hospital group
    HospitalGroupSubscription.objects.get_or_create(user=request.user, hospital_group=group)
    
    if created:
        messages.success(request, f'You have joined {group.name}!')
    else:
        messages.info(request, f'You are already a member of {group.name}.')
    
    return redirect('community:group_detail', pk=pk)


@login_required
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
    is_member = GroupMember.objects.filter(group=group, user=request.user).exists()
    if group.is_private and not is_member:
        messages.error(request, 'You do not have access to this content.')
        return redirect('community:group_list')
    
    schedules = group.hospital.clinic_schedules.filter(
        scheduled_date__gte=timezone.now().date()
    ).order_by('scheduled_date')
    
    return render(request, 'clinic_schedules.html', {
        'group': group,
        'schedules': schedules,
        'is_member': is_member
    })


@login_required
def create_clinic_schedule(request, group_id):
    """Hospital staff create clinic schedules"""
    group = get_object_or_404(HospitalGroup, pk=group_id)
    
    # Check if user is authorized (hospital staff)
    if group.hospital.user != request.user and not GroupMember.objects.filter(
        group=group, 
        user=request.user, 
        role__in=['DOCTOR', 'NURSE', 'ADMIN']
    ).exists():
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
def view_notifications(request):
    """View user's community notifications"""
    notifications = CommunityNotification.objects.filter(user=request.user).order_by('-created_at')
    
    if request.method == 'POST':
        # Mark all as read
        notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, 'All notifications marked as read.')
        return redirect('community:view_notifications')
    
    return render(request, 'community_notifications.html', {
        'notifications': notifications,
        'unread_count': notifications.filter(is_read=False).count()
    })