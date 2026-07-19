from django.db import models
from django.conf import settings
from accounts.models import *

User = settings.AUTH_USER_MODEL


class ForumCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class ForumPost(models.Model):

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='forum_posts'
    )

    category = models.ForeignKey(
        ForumCategory,
        on_delete=models.SET_NULL,
        null=True
    )

    title = models.CharField(max_length=255)

    content = models.TextField()

    is_anonymous = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    

class ForumAttachment(models.Model):

    post = models.ForeignKey(
        ForumPost,
        on_delete=models.CASCADE,
        related_name='attachments'
    )

    file = models.FileField(upload_to='forum_attachments/')

    uploaded_at = models.DateTimeField(auto_now_add=True)


class ForumComment(models.Model):

    post = models.ForeignKey(
        ForumPost,
        on_delete=models.CASCADE,
        related_name='comments'
    )

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.author} - {self.post}'
    


class ForumReaction(models.Model):

    class Reaction(models.TextChoices):
        SUPPORT = "SUPPORT", "Support"
        HUG = "HUG", "Hug"
        STRONG = "STRONG", "Stay Strong"
        LOVE = "LOVE", "Love"

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    post = models.ForeignKey(
        ForumPost,
        on_delete=models.CASCADE,
        related_name='reactions'
    )

    reaction = models.CharField(
        max_length=20,
        choices=Reaction.choices
    )

    class Meta:
        unique_together = ('user', 'post')



class HospitalGroup(models.Model):

    hospital = models.ForeignKey(
        HospitalProfile,
        on_delete=models.CASCADE,
        related_name='groups'
    )

    name = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    is_private = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class GroupMember(models.Model):

    class Role(models.TextChoices):
        PATIENT = "PATIENT", "Patient"
        DOCTOR = "DOCTOR", "Doctor"
        NURSE = "NURSE", "Nurse"
        ADMIN = "ADMIN", "Admin"

    group = models.ForeignKey(
        HospitalGroup,
        on_delete=models.CASCADE,
        related_name='members'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'user')

class GroupPost(models.Model):

    group = models.ForeignKey(
        HospitalGroup,
        on_delete=models.CASCADE,
        related_name='posts'
    )

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)


class GroupAttachment(models.Model):

    post = models.ForeignKey(
        GroupPost,
        on_delete=models.CASCADE,
        related_name='attachments'
    )

    file = models.FileField(upload_to='group_attachments/')

    uploaded_at = models.DateTimeField(auto_now_add=True)


class GroupComment(models.Model):

    post = models.ForeignKey(
        GroupPost,
        on_delete=models.CASCADE,
        related_name='comments'
    )

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)


class ForumCommentAnonymous(models.Model):
    """Allow anonymous comments on forum posts"""
    post = models.ForeignKey(
        ForumPost,
        on_delete=models.CASCADE,
        related_name='anonymous_comments'
    )

    content = models.TextField()
    author_name = models.CharField(max_length=100, default="Anonymous")
    is_anonymous = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anonymous - {self.post.title}"


class ClinicSchedule(models.Model):
    """Hospital clinic schedules"""
    hospital = models.ForeignKey(
        HospitalProfile,
        on_delete=models.CASCADE,
        related_name='clinic_schedules'
    )

    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # Date and time fields
    scheduled_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    location = models.CharField(max_length=255, blank=True)
    specialization = models.CharField(max_length=100, blank=True)  # e.g., "Maternal Care", "Pediatrics"
    
    max_patients = models.IntegerField(default=20)
    available_slots = models.IntegerField(default=20)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_date', 'start_time']

    def __str__(self):
        return f"{self.hospital.name} - {self.title} ({self.scheduled_date})"


class ForumSubscription(models.Model):
    """Users can subscribe to forums for notifications"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_subscriptions')
    forum = models.ForeignKey(ForumCategory, on_delete=models.CASCADE, related_name='subscribers')
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'forum')

    def __str__(self):
        return f"{self.user.username} subscribed to {self.forum.name}"


class CommunityNotification(models.Model):
    """Notifications for forum and hospital updates"""
    NOTIFICATION_TYPES = [
        ('new_post', 'New Post'),
        ('new_comment', 'New Comment'),
        ('clinic_schedule', 'Clinic Schedule'),
        ('hospital_announcement', 'Hospital Announcement'),
        ('subscription_alert', 'Subscription Alert'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='community_notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # References
    forum_post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, null=True, blank=True)
    hospital_group = models.ForeignKey(HospitalGroup, on_delete=models.CASCADE, null=True, blank=True)
    clinic_schedule = models.ForeignKey(ClinicSchedule, on_delete=models.CASCADE, null=True, blank=True)
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"


class HospitalGroupSubscription(models.Model):
    """Users subscribe to hospital group notifications"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hospital_subscriptions')
    hospital_group = models.ForeignKey(HospitalGroup, on_delete=models.CASCADE, related_name='subscribers')
    subscribed_at = models.DateTimeField(auto_now_add=True)
    
    # Notification preferences
    notify_new_posts = models.BooleanField(default=True)
    notify_clinic_schedule = models.BooleanField(default=True)
    notify_announcements = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'hospital_group')

    def __str__(self):
        return f"{self.user.username} subscribed to {self.hospital_group.name}"