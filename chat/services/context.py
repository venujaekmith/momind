def build_context(user, message):
  
    # change and get weeks,phase,delivery_date dyanmically
    return {
        "role": user.role,
        "week": "5", 
        "phase": "postpaurem" ,
        "delivery_date": "2026/12/1" ,
        "message": message
    }