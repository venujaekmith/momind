import random

def generate_id(prefix):
    return f"{random.randint(100000, 999999)}{prefix}"