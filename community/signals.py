"""
Signals for Community app
- Auto-create hospital groups when hospital is created
- Auto-join mothers to hospital groups when they connect
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import HospitalProfile, Family
from .models import HospitalGroup, GroupMember, HospitalGroupSubscription


@receiver(post_save, sender=HospitalProfile)
def create_hospital_community_group(sender, instance, created, **kwargs):
    """
    Automatically create a community forum for each hospital
    """
    if created:
        HospitalGroup.objects.get_or_create(
            hospital=instance,
            defaults={
                'name': f'{instance.name} Community Forum',
                'description': f'Community forum for {instance.name}',
                'created_by': instance.user,
                'is_private': False  # Public by default
            }
        )


@receiver(post_save, sender=Family)
def auto_join_mother_to_hospital_group(sender, instance, created, **kwargs):
    """
    Automatically add mother to hospital group when family is created/updated
    """
    # If mother is connected to a hospital
    if instance.mother and instance.hospital:
        hospital_group = HospitalGroup.objects.filter(hospital=instance.hospital).first()
        
        if hospital_group:
            mother_user = instance.mother.user
            
            # Add mother as a member
            member, member_created = GroupMember.objects.get_or_create(
                group=hospital_group,
                user=mother_user,
                defaults={'role': 'PATIENT'}
            )
            
            # Auto-subscribe to hospital group
            HospitalGroupSubscription.objects.get_or_create(
                user=mother_user,
                hospital_group=hospital_group,
                defaults={
                    'notify_new_posts': True,
                    'notify_clinic_schedule': True,
                    'notify_announcements': True
                }
            )
    
    # If father is connected to a hospital
    if instance.father and instance.hospital:
        hospital_group = HospitalGroup.objects.filter(hospital=instance.hospital).first()
        
        if hospital_group:
            father_user = instance.father.user
            
            # Add father as a member
            member, member_created = GroupMember.objects.get_or_create(
                group=hospital_group,
                user=father_user,
                defaults={'role': 'PATIENT'}
            )
            
            # Auto-subscribe to hospital group
            HospitalGroupSubscription.objects.get_or_create(
                user=father_user,
                hospital_group=hospital_group
            )
    
    # If midwife is connected to hospital
    if instance.midwife and instance.hospital:
        hospital_group = HospitalGroup.objects.filter(hospital=instance.hospital).first()
        
        if hospital_group:
            midwife_user = instance.midwife.user
            
            # Add the linked midwife with group-management capability.
            member, member_created = GroupMember.objects.update_or_create(
                group=hospital_group,
                user=midwife_user,
                defaults={'role': GroupMember.Role.MIDWIFE}
            )
    
    # If doctor is connected to hospital
    if instance.doctor and instance.hospital:
        hospital_group = HospitalGroup.objects.filter(hospital=instance.hospital).first()
        
        if hospital_group:
            doctor_user = instance.doctor.user
            
            # Add doctor as staff
            member, member_created = GroupMember.objects.get_or_create(
                group=hospital_group,
                user=doctor_user,
                defaults={'role': 'DOCTOR'}
            )
