def safety_check(text):
    danger_signs = [
        "heavy bleeding",
        "no baby movement",
        "severe chest pain",
        "fainting",
        "high fever"
    ]

    for word in danger_signs:
        if word in text.lower():
            return True
    return False