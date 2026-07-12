from aiogram.fsm.state import StatesGroup, State

class LicenseState(StatesGroup):
    waiting_for_duration = State()
    waiting_for_custom_duration = State()
    waiting_for_delete_code = State()

class AdminState(StatesGroup):
    waiting_for_license = State()
    waiting_for_category_name = State()
    waiting_for_product_name = State()
    waiting_for_product_category = State() # اضافه شد
    waiting_for_product_photo = State()
    waiting_for_product_price = State()
    waiting_for_product_stock = State()
    waiting_for_delete_id = State()
    waiting_for_search_order = State()     # اضافه شد

class CustomerState(StatesGroup):
    waiting_for_quantity = State()
    waiting_for_profile_fullname = State() # پروفایل
    waiting_for_profile_phone = State()    # پروفایل
    waiting_for_profile_address = State()  # پروفایل
    waiting_for_receipt = State()