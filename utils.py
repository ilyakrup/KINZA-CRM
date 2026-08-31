import random
import re
import string
from datetime import datetime

def parse_and_validate_date(date_text: str) -> str | None:
    """Проверяет корректность даты (ДД.ММ) и исключает несуществующие дни."""
    cleaned = re.sub(r"[\/\-\s,]+", ".", date_text.strip())
    match = re.match(r"^(\d{1,2})\.(\d{1,2})(?:\.\d{2,4})?$", cleaned)
    if not match:
        return None
    
    day, month = int(match.group(1)), int(match.group(2))
    if not (1 <= month <= 12):
        return None
    
    days_in_months = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not (1 <= day <= days_in_months[month - 1]):
        return None
    
    return f"{day:02d}.{month:02d}"

def generate_promo_code(prefix: str = "KINZA") -> str:
    """Генерирует уникальный красивый промокод: например KINZA-WELCOME-7482"""
    digits = "".join(random.choices(string.digits, k=4))
    return f"{prefix}-{digits}"

def is_date_in_next_days(bday_str: str, days_range: int = 7) -> bool:
    """Проверяет, попадает ли день рождения в диапазон от сегодня до +N дней."""
    if not bday_str:
        return False
    try:
        day, month = map(int, bday_str.split("."))
        current_year = datetime.now().year
        bday_date = datetime(current_year, month, day).date()
        today = datetime.now().date()
        
        if bday_date < today:
            bday_date = datetime(current_year + 1, month, day).date()
            
        diff = (bday_date - today).days
        return 0 <= diff <= days_range
    except Exception:
        return False