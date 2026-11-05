from django.contrib import admin

from .models import *


# === Forum Admin ===
@admin.register(ForumCategory)
class ForumCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'subscribers_count']
    search_fields = ['name']
    
    def subscribers_count(self, obj):
        return obj.subscribers.count()
    subscribers_count.short_description = 'Subscribers'


@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'is_anonymous', 'category', 'created_at', 'comments_count']
    list_filter = ['is_anonymous', 'category', 'created_at']
    search_fields = ['title', 'content', 'author__username']
    readonly_fields = ['created_at', 'updated_at']
    
    def comments_count(self, obj):
        return obj.comments.count() + obj.anonymous_comments.count()
    comments_count.short_description = 'Comments'


@admin.register(ForumAttachment)
class ForumAttachmentAdmin(admin.ModelAdmin):
    list_display = ['post', 'uploaded_at']
    list_filter = ['uploaded_at']


@admin.register(ForumComment)
class ForumCommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'post', 'created_at']
    list_filter = ['created_at']
    search_fields = ['content', 'author__username']


@admin.register(ForumCommentAnonymous)
class ForumCommentAnonymousAdmin(admin.ModelAdmin):
    list_display = ['author_name', 'post', 'created_at']
    list_filter = ['created_at']
    search_fields = ['content', 'author_name']


@admin.register(ForumReaction)
class ForumReactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'post', 'reaction']
    list_filter = ['reaction']


# === Hospital Group Admin ===
@admin.register(HospitalGroup)
class HospitalGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'hospital', 'is_private', 'members_count', 'created_at']
    list_filter = ['is_private', 'created_at']
    search_fields = ['name', 'hospital__name']
    
    def members_count(self, obj):
        return obj.members.count()
    members_count.short_description = 'Members'


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'role', 'joined_at']
    list_filter = ['role', 'joined_at']
    search_fields = ['user__username', 'group__name']


@admin.register(GroupPost)
class GroupPostAdmin(admin.ModelAdmin):
    list_display = ['group', 'author', 'created_at', 'comments_count']
    list_filter = ['created_at', 'group']
    search_fields = ['content', 'author__username']
    
    def comments_count(self, obj):
        return obj.comments.count()
    comments_count.short_description = 'Comments'


@admin.register(GroupAttachment)
class GroupAttachmentAdmin(admin.ModelAdmin):
    list_display = ['post', 'uploaded_at']
    list_filter = ['uploaded_at']


@admin.register(GroupComment)
class GroupCommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'post', 'created_at']
    list_filter = ['created_at']


# === Clinic Schedule Admin ===
@admin.register(ClinicSchedule)
class ClinicScheduleAdmin(admin.ModelAdmin):
    list_display = ['title', 'hospital', 'scheduled_date', 'start_time', 'available_slots', 'created_at']
    list_filter = ['scheduled_date', 'hospital', 'specialization']
    search_fields = ['title', 'hospital__name', 'specialization']
    readonly_fields = ['created_at', 'updated_at']


# === Subscription Admin ===
@admin.register(ForumSubscription)
class ForumSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'forum', 'subscribed_at']
    list_filter = ['subscribed_at', 'forum']
    search_fields = ['user__username', 'forum__name']


@admin.register(HospitalGroupSubscription)
class HospitalGroupSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'hospital_group', 'notify_new_posts', 'notify_clinic_schedule', 'subscribed_at']
    list_filter = ['subscribed_at', 'hospital_group', 'notify_new_posts']
    search_fields = ['user__username', 'hospital_group__name']


# === Notification Admin ===
@admin.register(CommunityNotification)
class CommunityNotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    readonly_fields = ['created_at']
    
    def has_add_permission(self, request):
        # Notifications are created automatically
        return False