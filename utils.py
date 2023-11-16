
import datetime

def get_week_of_year():
    today = datetime.datetime.today()
    return today.isocalendar()[1]
