import asyncio
import logging
import sys
import django
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import  Message, InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from asgiref.sync import sync_to_async


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coder_movie_bot.settings')
django.setup()

from bot_admin.models import Channel, Movie, User
from coder_movie_bot import settings


bot = Bot(token=settings.TOKEN)
dp = Dispatcher()


logging.basicConfig(level=logging.INFO, handlers=[
    logging.StreamHandler(sys.stdout),
    logging.FileHandler('bot.log')
])


user_states = {}



# Utility functions
async def check_subscription(user_id):
    # Asynchronously retrieve all channels from the Django model
    channels = await sync_to_async(list)(Channel.objects.all())  # Convert the queryset to a list

    for channel in channels:
        try:
            # Check if the user is a member of the channel
            chat_member = await bot.get_chat_member(chat_id=channel.channel_url, user_id=user_id)
            if chat_member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            logging.error(f"Error checking subscription for channel {channel.channel_name}: {e}")
            return False
    return True



async def ensure_subscription(message: Message):
    user_id = message.from_user.id

    if not await check_subscription(user_id):
        # If user is not subscribed, remove all buttons and show the subscription prompt
        await send_subscription_prompt(message)
        return False  # Indicate that the user is not subscribed
    return True  # User is subscribed

async def get_inline_keyboard_for_channels():
    channels = Channel.objects.all()  # Using Django ORM to fetch all channels

    inline_keyboard = []
    for channel in channels:
        # Assuming `channel_name` and `channel_url` are fields in your Django model
        inline_keyboard.append([InlineKeyboardButton(text=f"{channel.channel_name}", url=channel.channel_url)])

    # Add "A'zo bo'ldim" button
    inline_keyboard.append([InlineKeyboardButton(text="A'zo bo'ldim", callback_data='azo')])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)




async def delete_previous_inline_message(chat_id, message_id):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as e:
        logging.error(f"Failed to delete previous inline message: {e}")

@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username  # Retrieve the username

    try:
        # Foydalanuvchini Django modeliga qo'shish
        await sync_to_async(User.objects.update_or_create)(
            telegram_id=user_id,
            defaults={'username': username}
        )
    except Exception as e:
        logging.error(f"Error adding user to Django model: {e}")
        await message.answer("Foydalanuvchini qo'shishda xatolik yuz berdi.")
        return

    if not await ensure_subscription(message):
        return  # Stop further execution if the user is not subscribed

    await command_start_handler(message, message.from_user.first_name)
async def send_subscription_prompt(message: Message):
    user_id = message.from_user.id

    # Remove old inline keyboard if exists
    if 'last_inline_message_id' in user_states.get(user_id, {}):
        await delete_previous_inline_message(message.chat.id, user_states[user_id]['last_inline_message_id'])

    inline_keyboard = get_inline_keyboard_for_channels()
    sent_message = await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=inline_keyboard)

    # Store the message ID for future reference
    user_states[user_id] = user_states.get(user_id, {})
    user_states[user_id]['last_inline_message_id'] = sent_message.message_id


@dp.callback_query(lambda c: c.data == 'azo')
async def callback_handler(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await check_subscription(user_id):
        await command_start_handler(callback_query.message, callback_query.from_user.first_name)
    else:
        await send_subscription_prompt(callback_query.message)

async def command_start_handler(message: Message, first_name: str):
    user_id = message.from_user.id

    if await check_subscription(user_id):
        is_admin = user_id in settings.ADMINS

        # Create admin buttons if the user is an admin
        admin_buttons = []
        if is_admin:
            admin_buttons = [
                [KeyboardButton(text="➕ Kino qo'shish")],
            ]

        # Create the main keyboard with admin buttons if applicable
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🤖 Telegram bot yasatish")],
                *admin_buttons
            ],
            resize_keyboard=True
        )
        user_states[user_id] = {'state': 'searching_movie'}
        await message.answer(f"<b>👋Salom {first_name}</b>\n\n<i>Kino kodini kiriting...</i>", reply_markup=keyboard, parse_mode='html')
    else:
        await send_subscription_prompt(message)


@dp.message(lambda message: message.text == "➕ Kino qo'shish")
async def add_movie_start(message: Message):
    user_id = message.from_user.id
    if user_id not in settings.ADMINS:
        await message.answer("Sizda kino qo'shish huquqi mavjud emas.")
        return
    user_states[message.from_user.id] = {'state': 'adding_movie', 'step': 'title'}
    await message.answer("Kino nomini yuboring.", reply_markup=only_back_keyboard())

@dp.message(lambda message: message.text == "🤖 Telegram bot yasatish")
async def telegram_service_request(message: Message):
    user_id = message.from_user.id
    t = ("<b>🤖Telegram bot yaratish xizmati🤖</b>\n\n"
         "Admin: @otabek_mma1\n\n"
         "<i>Adminga bot nima haqida\n"
         "bot qanday vazifalarni bajarish kerak\n"
         "toliq malumot yozib qo'ying</i>\n\n"
         "Shunga qarab narxi kelishiladi")
    await message.answer(text=t, parse_mode='html')
async def save_movie_to_db(user_id):
    movie_data = user_states.get(user_id)
    if not movie_data:
        return False

    try:
        await sync_to_async(Movie.objects.create)(
            title=movie_data['title'],
            year=movie_data['year'],
            genre=movie_data['genre'],
            language=movie_data['language'],
            code=movie_data['code'],
            video_file_id=movie_data['video_file_id']
        )
        return True
    except Exception as e:
        logging.error(f"Error saving movie to database: {e}")
        return False

def only_back_keyboard():
    # Implement this function to provide a keyboard with a back button
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔙 Orqaga")]
    ], resize_keyboard=True)

# Handler for adding movie
@dp.message(lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id].get('state') == 'adding_movie')
async def add_movie(message: Message):
    user_id = message.from_user.id
    state = user_states[user_id]['step']

    if message.text == "🔙 Orqaga":
        await command_start_handler(message, message.from_user.first_name)
        return

    if state == 'title':
        user_states[user_id]['title'] = message.text
        user_states[user_id]['step'] = 'year'
        await message.answer("Kino yilini yuboring.", reply_markup=only_back_keyboard())
    elif state == 'year':
        try:
            user_states[user_id]['year'] = int(message.text)
            user_states[user_id]['step'] = 'genre'
            await message.answer("Kino janrini yuboring.", reply_markup=only_back_keyboard())
        except ValueError:
            await message.answer("Yil raqam bo'lishi kerak. Iltimos, qaytadan kiriting.")
    elif state == 'genre':
        user_states[user_id]['genre'] = message.text
        user_states[user_id]['step'] = 'language'
        await message.answer("Kino tilini yuboring.", reply_markup=only_back_keyboard())
    elif state == 'language':
        user_states[user_id]['language'] = message.text
        user_states[user_id]['step'] = 'code'
        await message.answer("Kino kodini yuboring.", reply_markup=only_back_keyboard())
    elif state == 'code':
        user_states[user_id]['code'] = message.text
        user_states[user_id]['step'] = 'video'
        await message.answer("Kino videosini yuklang (faqat MP4 format).", reply_markup=only_back_keyboard())
    elif state == 'video':
        if message.video and message.video.mime_type == 'video/mp4':
            file_id = message.video.file_id

            # Save the movie details including the video file ID to the database
            user_states[user_id]['video_file_id'] = file_id
            if await save_movie_to_db(user_id):
                await message.answer(f"Kino muvaffaqiyatli qo'shildi: {user_states[user_id]['title']}")
            else:
                await message.answer("Kino qo'shishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

            # Clear user state and go back to the admin panel
            user_states.pop(user_id, None)
            await command_start_handler(message, message.from_user.first_name)
        else:
            await message.answer("Iltimos, MP4 formatidagi videoni yuboring.")

async def search_movie_by_code(message: Message):
    user_id = message.from_user.id
    movie_code = message.text.strip()

    try:
        # Django modeli orqali asinxron kino qidiramiz
        movie = await sync_to_async(Movie.objects.filter(code=movie_code).first)()

    except Exception as e:
        logging.error(f"Database error: {e}")
        await message.answer("Ma'lumotlar bazasiga ulanishda xatolik. Iltimos, keyinroq qayta urinib ko'ring.")
        return

    if movie:
        caption = (
            f"<b>🎬Nomi:</b> {movie.title}\n\n"
            f"<b>📆Yili:</b> {movie.year}\n"
            f"<b>🎞Janr:</b> {movie.genre}\n"
            f"<b>🌍Tili:</b> {movie.language}\n"
            f"<b>🗂Yuklash:</b> {movie.code}\n\n\n"
            f"<b>🤖Bot:</b> @codermoviebot"
        )

        if movie.video_file_id:
            try:
                # Video faylni asinxron yuborish
                await bot.send_video(chat_id=user_id, video=movie.video_file_id, caption=caption, parse_mode='HTML')
            except Exception as e:
                logging.error(f"Error sending video: {e}")
                await message.answer("Videoni jo'natishda xatolik yuz berdi.")
        else:
            await message.answer("Kino videosi topilmadi.")
    else:
        await message.answer("Kino topilmadi. Iltimos, kodni to'g'ri kiriting yoki qayta urinib ko'ring.")

    # Foydalanuvchidan yana kod kiritishini so'raymiz
    user_states[user_id] = {'state': 'searching_movie'}

# Holatni tekshiradigan handler
@dp.message(lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id].get('state') == 'searching_movie')
async def search_movie_by_code_handler(message: Message):
    await search_movie_by_code(message)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
