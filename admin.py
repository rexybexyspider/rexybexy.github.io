import jdatetime
from datetime import datetime, timedelta
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func
from config import ADMIN_ID
from database import async_session, License, Category, Product, Order
from states import AdminState

router = Router()
router.message.filter(F.from_user.id == ADMIN_ID)

# --- بررسی لایسنس ---
async def check_admin_license() -> bool:
    async with async_session() as session:
        result = await session.execute(select(License).where(License.activated_by == ADMIN_ID, License.is_used == True))
        active_license = result.scalar_one_or_none()
        if active_license and active_license.expires_at > datetime.utcnow(): 
            return True
        return False

# --- کیبورد اصلی ادمین ---
def get_admin_keyboard():
    kb = [
        [types.KeyboardButton(text="🛒 سفارش‌های جدید"), types.KeyboardButton(text="✅ سفارش‌های تایید شده")],
        [types.KeyboardButton(text="🔍 جستجوی سفارش"), types.KeyboardButton(text="📜 تاریخچه سفارشات")],
        [types.KeyboardButton(text="➕ افزودن محصول"), types.KeyboardButton(text="📦 مدیریت محصولات")],
        [types.KeyboardButton(text="➕ افزودن دسته‌بندی"), types.KeyboardButton(text="🗂 مدیریت دسته‌بندی‌ها")],
        [types.KeyboardButton(text="📊 گزارش درآمد"), types.KeyboardButton(text="🔑 وضعیت لایسنس")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@router.message(F.text.in_(["/start", "🔙 بازگشت به منوی اصلی"]))
async def admin_start(message: types.Message, state: FSMContext):
    await state.clear()
    if not await check_admin_license():
        kb = [[types.KeyboardButton(text="🔓 فعال‌سازی لایسنس")]]
        await message.answer("❌ لایسنس شما معتبر نیست.", reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))
    else:
        await message.answer("🏪 **پنل مدیریت فروشگاه**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")

# ==========================================
# بخش مدیریت لایسنس
# ==========================================
@router.message(F.text.contains("فعال‌سازی لایسنس"))
async def ask_for_license(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🔑 کد لایسنس را ارسال کنید:")
    await state.set_state(AdminState.waiting_for_license)

@router.message(AdminState.waiting_for_license)
async def activate_license(message: types.Message, state: FSMContext):
    async with async_session() as session:
        result = await session.execute(select(License).where(License.code == message.text.strip().upper(), License.is_used == False))
        db_license = result.scalar_one_or_none()
        if db_license:
            db_license.is_used = True
            db_license.activated_by = ADMIN_ID
            db_license.expires_at = datetime.utcnow() + timedelta(days=db_license.duration_days)
            await session.commit()
            await message.answer("✅ لایسنس با موفقیت فعال شد!")
            await admin_start(message, state)
        else: 
            await message.answer("❌ کد لایسنس نامعتبر است یا قبلاً استفاده شده.")

@router.message(F.text.contains("وضعیت لایسنس"))
async def license_status(message: types.Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        result = await session.execute(select(License).where(License.activated_by == ADMIN_ID, License.is_used == True))
        lic = result.scalar_one_or_none()
        if lic and lic.expires_at > datetime.utcnow():
            jalali_date = jdatetime.datetime.fromgregorian(datetime=lic.expires_at).strftime("%Y/%m/%d")
            await message.answer(f"✅ **لایسنس شما فعال است**\nکد: `{lic.code}`\nتاریخ انقضا (شمسی): **{jalali_date}**", parse_mode="Markdown")
        else: 
            await message.answer("❌ لایسنس شما منقضی شده است.")

# ==========================================
# بخش مدیریت دسته‌بندی‌ها
# ==========================================
@router.message(F.text.contains("افزودن") & F.text.contains("دسته"))
async def add_cat(m: types.Message, state: FSMContext):
    await state.clear() # شکستن قفل وضعیت‌های قبلی برای رفع باگ هاست
    await m.answer("🗂 نام دسته‌بندی جدید را وارد کنید:")
    await state.set_state(AdminState.waiting_for_category_name)

@router.message(AdminState.waiting_for_category_name)
async def save_cat(m: types.Message, state: FSMContext):
    async with async_session() as session:
        session.add(Category(name=m.text.strip()))
        await session.commit()
    await m.answer("✅ دسته‌بندی با موفقیت ثبت شد.")
    await admin_start(m, state)

@router.message(F.text.contains("مدیریت") & F.text.contains("دسته"))
async def view_cats(m: types.Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        cats = (await session.execute(select(Category))).scalars().all()
        if not cats:
            return await m.answer("لیست دسته‌بندی‌ها خالی است.")
        
        builder = InlineKeyboardBuilder()
        for c in cats:
            builder.button(text=f"🗑 حذف {c.name}", callback_data=f"delcat_{c.id}")
        builder.adjust(1)
        await m.answer("🗂 لیست دسته‌بندی‌ها:\n(برای حذف روی دکمه مربوطه کلیک کنید)", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("delcat_"))
async def delete_category(call: types.CallbackQuery):
    cat_id = int(call.data.split("_")[1])
    async with async_session() as session:
        cat = await session.get(Category, cat_id)
        if cat:
            prods = (await session.execute(select(Product).where(Product.category_id == cat_id))).scalars().all()
            for p in prods:
                p.category_id = None
            await session.delete(cat)
            await session.commit()
            await call.answer("✅ دسته‌بندی با موفقیت حذف شد.", show_alert=True)
            await call.message.delete()
        else:
            await call.answer("❌ دسته‌بندی یافت نشد.", show_alert=True)

# ==========================================
# بخش مدیریت محصولات
# ==========================================
@router.message(F.text.contains("افزودن") & F.text.contains("محصول"))
async def add_prod(m: types.Message, state: FSMContext):
    await state.clear() # شکستن قفل وضعیت‌های قبلی برای رفع باگ هاست
    await m.answer("📦 نام محصول را وارد کنید:")
    await state.set_state(AdminState.waiting_for_product_name)

@router.message(AdminState.waiting_for_product_name)
async def get_prod_category(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text.strip())
    async with async_session() as session:
        cats = (await session.execute(select(Category))).scalars().all()
        if not cats:
            await state.clear()
            return await m.answer("❌ ابتدا باید یک دسته‌بندی ایجاد کنید تا بتوانید محصول اضافه کنید!")
        
        builder = InlineKeyboardBuilder()
        for c in cats:
            builder.button(text=c.name, callback_data=f"setcat_{c.id}")
        builder.adjust(2)
        await m.answer("🗂 دسته‌بندی این محصول را انتخاب کنید:", reply_markup=builder.as_markup())
        await state.set_state(AdminState.waiting_for_product_category)

@router.callback_query(AdminState.waiting_for_product_category, F.data.startswith("setcat_"))
async def get_photo(call: types.CallbackQuery, state: FSMContext):
    cat_id = int(call.data.split("_")[1])
    await state.update_data(category_id=cat_id)
    await call.message.edit_text("🖼 حالا عکس محصول را بفرستید:")
    await state.set_state(AdminState.waiting_for_product_photo)

@router.message(AdminState.waiting_for_product_photo, F.photo)
async def get_price(m: types.Message, state: FSMContext):
    await state.update_data(photo=m.photo[-1].file_id)
    await m.answer("💰 قیمت محصول (به عدد):")
    await state.set_state(AdminState.waiting_for_product_price)

@router.message(AdminState.waiting_for_product_price)
async def get_stock(m: types.Message, state: FSMContext):
    if not m.text.isdigit():
        return await m.answer("❌ لطفا قیمت را فقط به صورت عدد وارد کنید.")
    await state.update_data(price=int(m.text))
    await m.answer("📦 موجودی انبار (به عدد):")
    await state.set_state(AdminState.waiting_for_product_stock)

@router.message(AdminState.waiting_for_product_stock)
async def save_prod(m: types.Message, state: FSMContext):
    if not m.text.isdigit():
        return await m.answer("❌ لطفا موجودی را فقط به صورت عدد وارد کنید.")
    d = await state.get_data()
    async with async_session() as session:
        session.add(Product(name=d['name'], category_id=d['category_id'], photo_id=d['photo'], price=d['price'], stock=int(m.text)))
        await session.commit()
    await m.answer("✅ محصول با موفقیت در فروشگاه ثبت شد.")
    await admin_start(m, state)

@router.message(F.text.contains("مدیریت") & F.text.contains("محصول"))
async def view_prods(m: types.Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        prods = (await session.execute(select(Product))).scalars().all()
        if not prods:
            return await m.answer("در حال حاضر محصولی در فروشگاه وجود ندارد.")
        
        await m.answer("📦 لیست محصولات شما:")
        for p in prods:
            builder = InlineKeyboardBuilder()
            builder.button(text="🗑 حذف این محصول", callback_data=f"delprod_{p.id}")
            text = f"کد: {p.id} | {p.name}\n💰 قیمت: {p.price}\n📦 موجودی: {p.stock} عدد"
            if p.photo_id:
                await m.answer_photo(p.photo_id, caption=text, reply_markup=builder.as_markup())
            else:
                await m.answer(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("delprod_"))
async def delete_product(call: types.CallbackQuery):
    prod_id = int(call.data.split("_")[1])
    async with async_session() as session:
        prod = await session.get(Product, prod_id)
        if prod:
            await session.delete(prod)
            await session.commit()
            await call.answer("✅ محصول با موفقیت حذف شد.", show_alert=True)
            await call.message.delete()
        else:
            await call.answer("❌ محصول یافت نشد.", show_alert=True)

# ==========================================
# بخش مدیریت سفارشات
# ==========================================
@router.message(F.text.contains("سفارش‌های جدید"))
async def pending_orders(message: types.Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.status == "pending"))
        orders = result.scalars().all()
        if not orders: 
            return await message.answer("🛒 در حال حاضر سفارش جدیدی ندارید.")
        await message.answer("سفارشات جدید در لحظه ثبت با عکس رسیدشان در همین چت برای شما ارسال شده‌اند.")

@router.message(F.text.contains("تایید شده"))
async def approved_orders(message: types.Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.status == "approved").order_by(Order.created_at.desc()))
        orders = result.scalars().all()
        if not orders: 
            return await message.answer("لیست سفارشات تایید شده خالی است.")
        text = "✅ **سفارشات تایید شده:**\n\n"
        for o in orders: 
            text += f"کد: {o.id} | مشتری: {o.fullname} | مبلغ: {o.total_price} | 📍 آدرس: {o.address}\n\n"
        await message.answer(text, parse_mode="Markdown")

@router.message(F.text.contains("تاریخچه"))
async def all_orders_history(message: types.Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        orders = (await session.execute(select(Order).order_by(Order.created_at.desc()))).scalars().all()
        if not orders: 
            return await message.answer("هیچ سفارشی تا کنون ثبت نشده است.")
        text = "📜 **تاریخچه کل سفارشات:**\n\n"
        for o in orders:
            status = "⏳" if o.status == "pending" else "✅" if o.status == "approved" else "❌"
            text += f"{status} کد: {o.id} | مشتری: {o.fullname} | مبلغ: {o.total_price} | 📍 آدرس: {o.address}\n"
        await message.answer(text, parse_mode="Markdown")

@router.message(F.text.contains("گزارش درآمد"))
async def revenue(message: types.Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        total = (await session.execute(select(func.sum(Order.total_price)).where(Order.status == "approved"))).scalar() or 0
        await message.answer(f"📊 **کل درآمد فروشگاه از سفارشات تایید شده:** {total} تومان", parse_mode="Markdown")

# ==========================================
# بخش جستجوی پیشرفته سفارش
# ==========================================
@router.message(F.text.contains("جستجوی سفارش"))
async def search_order_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🔢 لطفا کد پیگیری (ID) سفارش مورد نظر را ارسال کنید:")
    await state.set_state(AdminState.waiting_for_search_order)

@router.message(AdminState.waiting_for_search_order)
async def perform_search(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ کد پیگیری سفارش باید فقط شامل اعداد باشد.")
    
    async with async_session() as session:
        order = await session.get(Order, int(message.text))
        if order:
            status = "⏳ در انتظار بررسی" if order.status == "pending" else "✅ تایید شده" if order.status == "approved" else "❌ لغو شده"
            text = (f"🧾 **اطلاعات سفارش {order.id}:**\n\n"
                    f"👤 مشتری: {order.fullname}\n"
                    f"📍 آدرس دقیق: {order.address}\n"
                    f"💰 مبلغ نهایی: {order.total_price} تومان\n"
                    f"📌 وضعیت فعلی: **{status}**")
            if order.receipt_photo_id:
                await message.answer_photo(photo=order.receipt_photo_id, caption=text, parse_mode="Markdown")
            else:
                await message.answer(text, parse_mode="Markdown")
        else:
            await message.answer("❌ سفارشی با این کد یافت نشد.")
    await admin_start(message, state)

# ==========================================
# دکمه‌های شیشه‌ای تایید و رد سفارش
# ==========================================
@router.callback_query(F.data.startswith("approve_"))
async def approve_order_cb(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        order = await session.get(Order, order_id)
        if order and order.status == "pending":
            order.status = "approved"
            await session.commit()
            await callback.message.delete()
            await callback.answer("✅ سفارش تایید شد.", show_alert=True)
            await callback.bot.send_message(order.user_id, f"✅ کاربر گرامی، سفارش `{order_id}` شما تایید شد و به زودی به آدرس ثبت شده ارسال می‌گردد!", parse_mode="Markdown")
        else:
            await callback.answer("وضعیت این سفارش قبلاً تغییر کرده است.", show_alert=True)

@router.callback_query(F.data.startswith("reject_"))
async def reject_order_cb(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        order = await session.get(Order, order_id)
        if order and order.status == "pending":
            order.status = "rejected"
            await session.commit()
            await callback.message.delete()
            await callback.answer("❌ سفارش لغو شد.", show_alert=True)
            await callback.bot.send_message(order.user_id, f"❌ کاربر گرامی، متاسفانه سفارش `{order_id}` شما لغو شد.", parse_mode="Markdown")
        else:
            await callback.answer("وضعیت این سفارش قبلاً تغییر کرده است.", show_alert=True)