import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database import init_db
import owner, admin, customer

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()
    
    # حذف کامل بخش session و پراکسی
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    dp.include_router(owner.router)
    dp.include_router(admin.router)
    dp.include_router(customer.router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())