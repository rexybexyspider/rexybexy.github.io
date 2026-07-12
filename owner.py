import random
import string
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from config import OWNER_ID
from states import LicenseState
from database import async_session, License

router = Router()
router.message.filter(F.from_user.id == OWNER_ID)

@router.message(F.text == "/start")
async def owner_start(message: types.Message, state: FSMContext):
    await state.clear()
    kb = [
        [types.KeyboardButton(text="🔑 ایجاد لایسنس جدید")],
        [types.KeyboardButton(text="📋 مشاهده لایسنس‌ها"), types.KeyboardButton(text="🗑 حذف لایسنس")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("👑 **مدیریت کل سیستم (Owner)**\n\nبه پنل مدیریت خوش آمدید.", parse_mode="Markdown", reply_markup=keyboard)

@router.message(F.text == "🔑 ایجاد لایسنس جدید")
async def create_license_start(message: types.Message, state: FSMContext):
    kb = [
        [types.KeyboardButton(text="30 روزه"), types.KeyboardButton(text="90 روزه")],
        [types.KeyboardButton(text="180 روزه"), types.KeyboardButton(text="365 روزه")],
        [types.KeyboardButton(text="✍️ زمان دلخواه (دستی)"), types.KeyboardButton(text="🔙 بازگشت")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("⏱ **مدت زمان اعتبار لایسنس را انتخاب کنید:**", parse_mode="Markdown", reply_markup=keyboard)
    await state.set_state(LicenseState.waiting_for_duration)

@router.message(LicenseState.waiting_for_duration)
async def generate_license_or_custom(message: types.Message, state: FSMContext):
    text = message.text
    if text == "🔙 بازگشت":
        return await owner_start(message, state)
    if text == "✍️ زمان دلخواه (دستی)":
        await message.answer("🔢 تعداد روزهای اعتبار لایسنس را به عدد وارد کنید:", reply_markup=types.ReplyKeyboardRemove())
        return await state.set_state(LicenseState.waiting_for_custom_duration)

    duration_str = text.split()[0]
    if not duration_str.isdigit():
        return await message.answer("❌ گزینه معتبر نیست.")
    await create_and_send_license(message, state, int(duration_str))

@router.message(LicenseState.waiting_for_custom_duration)
async def generate_custom_license(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ فقط عدد وارد کنید:")
    await create_and_send_license(message, state, int(message.text))

async def create_and_send_license(message: types.Message, state: FSMContext, duration: int):
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    async with async_session() as session:
        new_license = License(code=code, duration_days=duration)
        session.add(new_license)
        await session.commit()
    await message.answer(f"✅ **لایسنس تولید شد!**\n\nکد: `{code}`\nاعتبار: {duration} روز", parse_mode="Markdown")
    await owner_start(message, state)

# --- مشاهده لایسنس‌ها ---
@router.message(F.text == "📋 مشاهده لایسنس‌ها")
async def view_licenses(message: types.Message):
    async with async_session() as session:
        result = await session.execute(select(License))
        licenses = result.scalars().all()
        
        if not licenses:
            return await message.answer("هیچ لایسنسی در سیستم ثبت نشده است.")
            
        text = "📋 **لیست تمام لایسنس‌ها:**\n\n"
        for lic in licenses:
            status = "🔴 استفاده شده" if lic.is_used else "🟢 آزاد"
            text += f"کد: `{lic.code}` | {lic.duration_days} روز | {status}\n"
            
        await message.answer(text, parse_mode="Markdown")

# --- حذف لایسنس ---
@router.message(F.text == "🗑 حذف لایسنس")
async def delete_license_start(message: types.Message, state: FSMContext):
    kb = [[types.KeyboardButton(text="🔙 بازگشت")]]
    await message.answer("🗑 **کد 10 رقمی لایسنسی که قصد حذف آن را دارید بفرستید:**", reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True), parse_mode="Markdown")
    await state.set_state(LicenseState.waiting_for_delete_code)

@router.message(LicenseState.waiting_for_delete_code)
async def delete_license_confirm(message: types.Message, state: FSMContext):
    if message.text == "🔙 بازگشت":
        return await owner_start(message, state)
        
    code = message.text.strip().upper()
    async with async_session() as session:
        result = await session.execute(select(License).where(License.code == code))
        db_license = result.scalar_one_or_none()
        
        if db_license:
            await session.delete(db_license)
            await session.commit()
            await message.answer(f"✅ لایسنس `{code}` با موفقیت حذف شد.", parse_mode="Markdown")
        else:
            await message.answer("❌ این لایسنس در دیتابیس یافت نشد.")
            
    await owner_start(message, state)