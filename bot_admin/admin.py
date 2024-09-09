from django.contrib import admin
from .models import Channel, Movie, User
from aiogram import Bot
from aiogram.types import InputFile
from django.conf import settings

bot = Bot(token=settings.TOKEN)  # Telegram bot tokenini sozlash

@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'url')

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('title', 'year', 'genre', 'language', 'code')
    actions = ['upload_video']

    def upload_video(self, request, queryset):
        for movie in queryset:
            video_path = movie.video_file.path  # Video faylning yo‘li
            input_file = InputFile(video_path)

            try:
                # Telegram serveriga video faylni yuborish
                message = bot.send_video(chat_id='@botadminch', video=input_file)
                file_id = message.video.file_id  # Video faylning file_id sini olish

                # Movie modelini yangilash
                movie.video_file_id = file_id
                movie.save()
            except Exception as e:
                self.message_user(request, f"Error uploading video: {e}", level='error')

        self.message_user(request, "Selected videos have been uploaded and file_id has been saved.")

    upload_video.short_description = "Upload selected videos to Telegram and save file_id"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'username')
