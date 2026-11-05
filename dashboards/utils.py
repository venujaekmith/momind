# dashboard/utils.py
from .models import *
from datetime import timedelta
from django.utils import timezone

def get_baby_size_info(week):
    data = {
        0:  {"size": "Poppy seed", "length": "Less than 0.1 cm", "weight": "Less than 1g"},
        # --- FIRST TRIMESTER ---
        1:  {"size": "Poppy seed", "length": "0.1 cm", "weight": "Less than 1g"},
        2:  {"size": "Poppy seed", "length": "0.1 cm", "weight": "Less than 1g"},
        3:  {"size": "Poppy seed", "length": "0.15 cm", "weight": "Less than 1g"},
        4:  {"size": "Poppy seed", "length": "0.2 cm", "weight": "Less than 1g"},
        5:  {"size": "Appleseed", "length": "0.33 cm", "weight": "Less than 1g"},
        6:  {"size": "Sweet pea", "length": "0.63 cm", "weight": "Less than 1g"},
        7:  {"size": "Blueberry", "length": "1.3 cm", "weight": "Less than 1g"},
        8:  {"size": "Raspberry", "length": "1.6 cm", "weight": "1g"},
        9:  {"size": "Green olive", "length": "2.3 cm", "weight": "2g"},
        10: {"size": "Prune", "length": "3.1 cm", "weight": "4g"},
        11: {"size": "Lime", "length": "4.1 cm", "weight": "7g"},
        12: {"size": "Plum", "length": "5.4 cm", "weight": "14g"},
        13: {"size": "Lemon", "length": "7.4 cm", "weight": "23g"},

        # --- SECOND TRIMESTER ---
        14: {"size": "Nectarine", "length": "8.7 cm", "weight": "43g"},
        15: {"size": "Apple", "length": "10.1 cm", "weight": "70g"},
        16: {"size": "Avocado", "length": "11.6 cm", "weight": "100g"},
        17: {"size": "Pomegranate", "length": "13.0 cm", "weight": "140g"},
        18: {"size": "Artichoke", "length": "14.2 cm", "weight": "190g"},
        19: {"size": "Mango", "length": "15.3 cm", "weight": "240g"},
        20: {"size": "Banana", "length": "25.6 cm", "weight": "300g"}, # Crown to heel from here
        21: {"size": "Carrot", "length": "26.7 cm", "weight": "360g"},
        22: {"size": "Papaya", "length": "27.8 cm", "weight": "430g"},
        23: {"size": "Grapefruit", "length": "28.9 cm", "weight": "501g"},
        24: {"size": "Cantaloupe", "length": "30.0 cm", "weight": "600g"},
        25: {"size": "Cauliflower", "length": "34.6 cm", "weight": "660g"},
        26: {"size": "Red cabbage", "length": "35.6 cm", "weight": "760g"},
        27: {"size": "Lettuce", "length": "36.6 cm", "weight": "875g"},

        # --- THIRD TRIMESTER (To Birth) ---
        28: {"size": "Eggplant", "length": "37.6 cm", "weight": "1.0kg"},
        29: {"size": "Butternut squash", "length": "38.6 cm", "weight": "1.2kg"},
        30: {"size": "Cabbage", "length": "39.9 cm", "weight": "1.3kg"},
        31: {"size": "Coconut", "length": "41.1 cm", "weight": "1.5kg"},
        32: {"size": "Jicama", "length": "42.4 cm", "weight": "1.7kg"},
        33: {"size": "Pineapple", "length": "43.7 cm", "weight": "1.9kg"},
        34: {"size": "Cantaloupe", "length": "45.0 cm", "weight": "2.1kg"},
        35: {"size": "Honeydew melon", "length": "46.2 cm", "weight": "2.4kg"},
        36: {"size": "Romaine lettuce", "length": "47.4 cm", "weight": "2.6kg"},
        37: {"size": "Winter melon", "length": "48.6 cm", "weight": "2.9kg"},
        38: {"size": "Leek", "length": "49.8 cm", "weight": "3.1kg"},
        39: {"size": "Watermelon", "length": "50.7 cm", "weight": "3.3kg"},
        40: {"size": "Pumpkin", "length": "51.2 cm", "weight": "3.4kg"},
    }
    
    if week is None:
        return None

    # Use the nearest supported comparison for boundary weeks.
    supported_week = max(0, min(int(week), 40))
    info = data[supported_week].copy()
    info["week"] = week
    return info



def create_postpartum_schedule(pregnancy):
    """Delete old schedules and create new postpartum + baby development schedule"""
    
    # 1. Delete all previous ScheduleEvents for this pregnancy
    ScheduleEvent.objects.filter(pregnancy=pregnancy).delete()

    today = timezone.now().date()
    baby = BabyProfile.objects.filter(pregnancy=pregnancy).first()

    default_postpartum_events = [
        # Midwife Visits (Postpartum)
        {"title": "1st Postpartum Midwife Visit (Day 3-7)", 
         "event_type": "midwife_visit", 
         "days": 5, 
         "notes": "Check mother's recovery, bleeding, and breastfeeding"},
        
        {"title": "2nd Postpartum Midwife Visit (Week 2)", 
         "event_type": "midwife_visit", 
         "days": 14, 
         "notes": "Mental health check and baby weight check"},
        
        {"title": "6-Week Postpartum Checkup", 
         "event_type": "midwife_visit", 
         "days": 42, 
         "notes": "Full recovery assessment + contraception advice"},

        # Baby Development & Mother Recovery
        {"title": "Daily Skin-to-Skin Contact", 
         "event_type": "milestone", 
         "days": 1, 
         "notes": "Aim for minimum 1 hour per day"},
        
        {"title": "Newborn Screening / Hearing Test", 
         "event_type": "hospital_clinic", 
         "days": 3, 
         "notes": "Usually done at hospital or clinic"},
        
        {"title": "Baby Weight Check (Week 2)", 
         "event_type": "midwife_visit", 
         "days": 14, 
         "notes": "Monitor baby's weight gain"},
        
        {"title": "Tummy Time Start", 
         "event_type": "milestone", 
         "days": 21, 
         "notes": "Start short tummy time sessions daily"},
        
        {"title": "6-Week Baby Development Review", 
         "event_type": "doctor_appointment", 
         "days": 42, 
         "notes": "Pediatric checkup + milestones review"},
        
        {"title": "Postpartum Mental Health Screening", 
         "event_type": "milestone", 
         "days": 30, 
         "notes": "Screen for postpartum depression"},
        
        {"title": "Baby Milestone - Social Smile", 
         "event_type": "milestone", 
         "days": 45, 
         "notes": "Expect baby to start smiling socially"},
    ]

    created_events = []
    for event in default_postpartum_events:
        scheduled_date = today + timedelta(days=event["days"])
        
        obj = ScheduleEvent.objects.create(
            pregnancy=pregnancy,
            title=event["title"],
            event_type=event["event_type"],
            scheduled_date=scheduled_date,
            notes=event["notes"],
            what_to_bring="Baby health card, mother's notes",
            created_by=pregnancy.mother.user,
            location="Home / Clinic",
            is_completed=False
        )
        created_events.append(obj)

    return created_events
