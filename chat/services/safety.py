def safety_check(text):
    text = " ".join(text.lower().replace("-", " ").split())
    danger_signs = (
        "heavy bleeding",
        "bleeding heavily",
        "no baby movement",
        "no fetal movement",
        "baby has stopped moving",
        "severe chest pain",
        "trouble breathing",
        "can't breathe",
        "cannot breathe",
        "fainting",
        "passed out",
        "seizure",
        "suicidal",
        "want to die",
        "hurt myself",
        "severe headache",
        "vision change",
        "blurred vision",
    )
    return any(sign in text for sign in danger_signs)