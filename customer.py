from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from config import OWNER_ID, ADMIN_ID, ADMIN_CARD_NUMBER
from database import async_session, Product, Order, User, Category
from states import CustomerState

router = Router()
router.message.filter(~F.from_user.id.in_([OWNER_ID, ADMIN_ID]))

def get_customer_kb():
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🛍 مشاهده فروشگاه")],
                  [types.KeyboardButton(text="👤 حساب کاربری من"), types.KeyboardButton(text="📜 تاریخچه سفارشات")]],
        resize_keyboard=True
    )

@router.message(F.text == "/start")
async def customer_start(message: types.Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            session.add(User(user_id=message.from_user.id, role="customer"))
            await session.commit()
            
    await message.answer("سلام! به فروشگاه ما خیلی خوش اومدی 🛒🌸\nاز منوی پایین می‌تونی کارهاتو انجام بدی.", reply_markup=get_customer_kb())

# --- منوی فروشگاه و دسته‌بندی‌ها ---
@router.message(F.text == "🛍 مشاهده فروشگاه")
async def show_store(message: types.Message):
    async with async_session() as session:
        cats = (await session.execute(select(Category))).scalars().all()
        if not cats:
            return await message.answer("در حال حاضر محصولی در فروشگاه نیست 😔")
            
        builder = InlineKeyboardBuilder()
        for c in cats:
            builder.button(text=f"📂 {c.name}", callback_data=f"viewcat_{c.id}")
        builder.adjust(2)
        
        await message.answer("دنبال چی می‌گردی؟ 😍\nدسته‌بندی مورد نظرت رو انتخاب کن:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("viewcat_"))
async def show_category_products(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        prods = (await session.execute(select(Product).where(Product.category_id == cat_id))).scalars().all()
        
        if not prods:
            return await callback.answer("این دسته‌بندی هنوز خالیه!", show_alert=True)
            
        await callback.message.delete()
        for p in prods:
            builder = InlineKeyboardBuilder()
            if p.stock > 0: builder.button(text="🛒 خرید", callback_data=f"buy_{p.id}")
            else: builder.button(text="❌ ناموجود", callback_data="none")
            
            cap = f"📦 {p.name}\n💰 قیمت: {p.price} تومان\n📊 موجودی: {p.stock} عدد"
            if p.photo_id: await callback.message.answer_photo(p.photo_id, caption=cap, reply_markup=builder.as_markup())
            else: await callback.message.answer(cap, reply_markup=builder.as_markup())

# --- پروفایل کاربری ---
@router.message(F.text == "👤 حساب کاربری من")
async def my_profile(message: types.Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user.fullname:
            text = "شما هنوز اطلاعات حساب کاربری خود را تکمیل نکرده‌اید."
        else:
            text = f"👤 نام: {user.fullname}\n📞 تماس: {user.phone}\n📍 آدرس: {user.address}"
            
        builder = InlineKeyboardBuilder()
        builder.button(text="✏️ ویرایش اطلاعات", callback_data="edit_profile")
        await message.answer(text, reply_markup=builder.as_markup())

# --- فرآیند خرید ---
@router.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        product = await session.get(Product, product_id)
        if not product or product.stock <= 0: return await callback.answer("❌ ناموجود است.", show_alert=True)
        
        await state.update_data(product_id=product.id, price=product.price, product_name=product.name)
        await callback.message.answer(f"قصد خرید **{product.name}** را دارید.\n🔢 **تعداد** را وارد کنید:", parse_mode="Markdown")
        await state.set_state(CustomerState.waiting_for_quantity)
        await callback.answer()

@router.message(CustomerState.waiting_for_quantity)
async def get_quantity(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("❌ عدد وارد کنید:")
    qty = int(message.text)
    
    data = await state.get_data()
    async with async_session() as session:
        product = await session.get(Product, data['product_id'])
        if qty > product.stock: return await message.answer(f"❌ موجودی فقط {product.stock} عدد است.")
        
        await state.update_data(qty=qty, total_price=qty * data['price'])
        user = await session.get(User, message.from_user.id)
        
        # --- رفع باگ هاست: اگر کاربر در دیتابیس نبود ثبتش کن ---
        if not user:
            user = User(user_id=message.from_user.id, role="customer")
            session.add(user)
            await session.commit()
        # --------------------------------------------------------

        if not user.fullname or not user.address:
            await message.answer("⚠️ برای ثبت سفارش ابتدا باید اطلاعات خود را تکمیل کنید.\n\n👤 لطفا **نام و نام خانوادگی** خود را بفرستید:")
            await state.set_state(CustomerState.waiting_for_profile_fullname)
        else:
            await generate_final_invoice(message, state, user)

# --- پر کردن فرم پروفایل ---
@router.callback_query(F.data == "edit_profile")
async def force_edit_profile(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("👤 لطفا **نام و نام خانوادگی** جدید خود را وارد کنید:")
    await state.set_state(CustomerState.waiting_for_profile_fullname)
    await call.answer()

@router.message(CustomerState.waiting_for_profile_fullname)
async def set_fullname(message: types.Message, state: FSMContext):
    await state.update_data(temp_fullname=message.text)
    await message.answer("📞 شماره تماس:")
    await state.set_state(CustomerState.waiting_for_profile_phone)

@router.message(CustomerState.waiting_for_profile_phone)
async def set_phone(message: types.Message, state: FSMContext):
    await state.update_data(temp_phone=message.text)
    await message.answer("📍 آدرس دقیق پستی:")
    await state.set_state(CustomerState.waiting_for_profile_address)

@router.message(CustomerState.waiting_for_profile_address)
async def set_address(message: types.Message, state: FSMContext):
    d = await state.get_data()
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        user.fullname = d['temp_fullname']
        user.phone = d['temp_phone']
        user.address = message.text
        await session.commit()
    
    await message.answer("✅ اطلاعات شما با موفقیت ذخیره شد.")
    # اگر کاربر در حال خرید بود، فاکتور را نشان بده
    if 'product_id' in d:
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            await generate_final_invoice(message, state, user)
    else:
        await state.clear()

# --- تولید فاکتور نهایی و آماده پرداخت ---
async def generate_final_invoice(message: types.Message, state: FSMContext, user: User):
    data = await state.get_data()
    msg = (f"🧾 **فاکتور نهایی شما**\n\n"
           f"📦 محصول: {data['product_name']}\n"
           f"🔢 تعداد: {data['qty']}\n"
           f"💰 مبلغ کل: **{data['total_price']} تومان**\n\n"
           f"👤 نام: {user.fullname}\n"
           f"📞 تماس: {user.phone}\n"
           f"📍 آدرس ارسال: {user.address}\n\n"
           f"💳 شماره کارت جهت واریز:\n`{ADMIN_CARD_NUMBER}`")
           
    builder = InlineKeyboardBuilder()
    builder.button(text="📸 آماده‌ام، ارسال رسید", callback_data="send_receipt")
    builder.button(text="✏️ ویرایش اطلاعات", callback_data="edit_profile")
    builder.adjust(1)
    
    await message.answer(msg, parse_mode="Markdown", reply_markup=builder.as_markup())

@router.callback_query(F.data == "send_receipt")
async def ask_for_receipt(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📸 لطفا تصویر رسید پرداختی خود را همینجا ارسال کنید:")
    await state.set_state(CustomerState.waiting_for_receipt)
    await call.answer()

@router.message(CustomerState.waiting_for_receipt, F.photo)
async def finalize_order(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    async with async_session() as session:
        product = await session.get(Product, data['product_id'])
        product.stock -= data['qty']
        user = await session.get(User, message.from_user.id)
        
        new_order = Order(user_id=user.user_id, fullname=user.fullname, address=user.address, total_price=data['total_price'], status="pending", receipt_photo_id=photo_id)
        session.add(new_order)
        await session.commit()
        order_id = new_order.id
        
    await message.answer(f"✅ **سفارش ثبت و در حالت انتظار می‌باشد.**\nپس از تایید مدیریت، پیام تایید برایتان ارسال می‌شود.\nشماره پیگیری: `{order_id}`", parse_mode="Markdown")
    
    # ارسال برای ادمین
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ تایید سفارش", callback_data=f"approve_{order_id}")
    builder.button(text="❌ لغو سفارش", callback_data=f"reject_{order_id}")
    
    admin_msg = (f"🛍 **سفارش جدید ({order_id})**\n👤 مشتری: {user.fullname}\n📦 {data['product_name']} ({data['qty']} عدد)\n"
                 f"💰 مبلغ: {data['total_price']} تومان\n📞 {user.phone}\n📍 آدرس: {user.address}")
    await message.bot.send_photo(ADMIN_ID, photo=photo_id, caption=admin_msg, reply_markup=builder.as_markup())
    await state.clear()