from math import floor

import requests
from sqlalchemy import func

avg_last_month_distance_customers = [1000 for i in range(12)]
number_of_users = 0
last_month = 0


def pointing(ride, user_count):
    this_month = func.month(func.current_date())
    ride_point = floor(ride.distance / avg_last_month_distance_customers[this_month - 1]) ^ 2 + 1
    ride_month = func.month(ride.date)
    avg_last_month_distance_customers[ride_month] = (avg_last_month_distance_customers[
                                                         ride_month] * user_count + ride_point) / user_count
    dictToSend = {"point": ride_point, "user_id": ride.customer_id}
    res = requests.get('http://localhost:5000//update_user', json=dictToSend)

    return {"point": ride_point, "msg": res.text}
