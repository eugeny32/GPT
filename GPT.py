import logging
import os
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import speech_recognition as sr
import openai
from moviepy.editor import AudioFileClip

# Установите ваш токен OpenAI API
openai.api_key = 'OpenAI API'

# Настройка логгирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)
logger = logging.getLogger(__name__)

# Количество доступных запросов в сутки
REQUESTS_LIMIT = 100

# Функция для обработки команды /start
def start(update, context):
    user_id = update.effective_user.id
    context.user_data[user_id] = {}  # Создаем словарь для пользователя
    context.user_data[user_id]['history'] = []  # Инициализация истории запросов
    context.user_data[user_id]['requests_left'] = REQUESTS_LIMIT  # Установка количества доступных запросов
    update.message.reply_text(
        'Я представляю собой бота, который предоставляет доступ к модели искусственного интеллекта. Вы можете задать вопрос в текстовом или голосовом формате, я постараюсь найти подходящий ответ или решение, основываясь на открытых источниках информации.',
        reply_markup=get_keyboard(context.user_data[user_id]['requests_left'])
    )

# Функция для обработки команды /help
def help_command(update, context):
    user_id = update.effective_user.id
    update.message.reply_text(
        "Вы можете взаимодействовать со мной следующими способами:\n\n"
        "1. Отправьте мне текстовое сообщение с вашим вопросом или задачей. Я постараюсь сгенерировать подробный ответ или предложить решение.\n"
        "2. Если вам удобнее выразить свой вопрос голосом, отправьте мне голосовое сообщение. Я преобразую его в текст и сгенерирую ответ или решение на основе содержания.\n"
        "3. В разработке на данный момент. Если у вас есть изображение или фотография, вы сможете отправить их мне. Я постараюсь анализировать изображение и предоставить вам соответствующий ответ или информацию.\n\n"
        "В любой момент вы можете очистить историю нашего диалога, отправив команду /clear. Это удалит все предыдущие запросы и ответы, и мы начнем с чистого листа.\n\n"
        "Не стесняйтесь задавать любые вопросы или пробовать разные способы взаимодействия со мной. Я здесь, чтобы помочь вам!"
    )

# Функция для обработки команды /contact
def contact_command(update, context):
    update.message.reply_text(
        "Если Вам есть что предложить для улучшения функциональных возможностей бота, не стесняйтесь обращаться к его разработчику: https://t.me/mtccom_ru"
    )

# Функция для генерации ответа от модели
def generate_response(prompt):
    response = openai.Completion.create(
        engine='text-davinci-003',
        prompt=prompt,
        max_tokens=2000
    )
    return response.choices[0].text.strip()

# Функция для обработки текстовых сообщений
def handle_message(update, context):
    user_id = update.effective_user.id
    user_input = update.message
    if user_input.text:
        if context.user_data[user_id]['requests_left'] <= 0:  # Проверка ограничения на количество запросов
            update.message.reply_text(
                'Вы превысили лимит доступных запросов. Пожалуйста, оплатите 2000 рублей для снятия ограничения.',
                reply_markup=get_payment_keyboard()
            )
        else:
            user_text = user_input.text
            bot_response = generate_response(user_text)
            if bot_response:
                context.user_data[user_id]['history'].append((user_text, bot_response))  # Добавление запроса и ответа в историю
                context.user_data[user_id]['requests_left'] -= 1  # Уменьшение количества доступных запросов
                update.message.reply_text(bot_response, reply_markup=get_keyboard(context.user_data[user_id]['requests_left']))
            else:
                update.message.reply_text(
                    'К сожалению, я не могу сгенерировать ответ на ваш вопрос. Попробуйте переформулировать его или задать другой вопрос.',
                    reply_markup=get_keyboard(context.user_data[user_id]['requests_left'])
                )
    elif user_input.voice:
        if context.user_data[user_id]['requests_left'] <= 0:  # Проверка ограничения на количество запросов
            update.message.reply_text(
                'Ого! Вы превысили лимит доступных запросов. Пожалуйста, оплатите 2000 рублей для снятия ограничения.',
                reply_markup=get_payment_keyboard()
            )
        else:
            file_id = user_input.voice.file_id
            file = context.bot.getFile(file_id)
            voice_file = f'voice_{file_id}.ogg'
            wav_file = f'voice_{file_id}.wav'
            file.download(voice_file)  # Загружаем файл голосового сообщения
            convert_to_wav(voice_file, wav_file)  # Преобразуем в WAV
            bot_response = generate_response_from_voice(wav_file)
            if bot_response:
                context.user_data[user_id]['history'].append((user_input.voice.file_id, bot_response))  # Добавление запроса и ответа в историю
                context.user_data[user_id]['requests_left'] -= 1  # Уменьшение количества доступных запросов
                update.message.reply_text(bot_response, reply_markup=get_keyboard(context.user_data[user_id]['requests_left']))
            else:
                update.message.reply_text(
                    'Ой! К сожалению, я не могу сгенерировать ответ на основе этото голосового сообщения. Попробуйте повторно задать вопрос голосом или сформулируйте его в текстом виде.',
                    reply_markup=get_keyboard(context.user_data[user_id]['requests_left'])
                )
            # Удаляем временные файлы
            os.remove(voice_file)
            os.remove(wav_file)

# Функция для преобразования аудиофайла в формат WAV
def convert_to_wav(input_file, output_file):
    try:
        audio = AudioFileClip(input_file)
        audio.write_audiofile(output_file, codec='pcm_s16le', bitrate='16k')
    except Exception as e:
        logger.error(f'Error converting audio to WAV: {e}')
        raise

# Функция для обработки голосового ввода
def generate_response_from_voice(voice_file):
    r = sr.Recognizer()
    with sr.AudioFile(voice_file) as source:
        try:
            audio = r.record(source)
            text = r.recognize_google(audio, language='ru-RU')
            return generate_response(text)
        except sr.UnknownValueError:
            return None
        except Exception as e:
            logger.error(f'Error recognizing voice input: {e}')
            raise

# Функция для удаления переписки с пользователем
def clear_history(update, context):
    user_id = update.effective_user.id
    context.user_data[user_id]['history'] = []  # Очищение истории запросов
    context.user_data[user_id]['requests_left'] = REQUESTS_LIMIT  # Сброс количества доступных запросов
    update.message.reply_text(
        'История диалога очищена.',
        reply_markup=get_keyboard(context.user_data[user_id]['requests_left'])
    )

# Функция для обработки ошибок
def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)

# Функция для создания клавиатуры с кнопками
def get_keyboard(requests_left):
    keyboard = [
        ['/start', '/help', '/clear', '/contact'],
        [f'Осталось запросов: {requests_left}']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Функция для создания клавиатуры с кнопкой оплаты
def get_payment_keyboard():
    keyboard = [[InlineKeyboardButton('Оплатить 2000 рублей', callback_data='payment')]]
    return InlineKeyboardMarkup(keyboard)

# Функция для обработки нажатия кнопки оплаты
def handle_payment(update, context):
    query = update.callback_query
    query.answer()
    query.message.reply_text('Для оплаты 2000 рублей, пожалуйста, перейдите по ссылке: https://yoomoney.ru/fundraise/9EfYUAO9AFo.230714&')

def main():
    # Установка токена Telegram бота
    updater = Updater("Установка токена Telegram бота", use_context=True)

    # Получаем диспетчер для регистрации обработчиков
    dp = updater.dispatcher

    # Регистрация обработчиков
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("clear", clear_history))
    dp.add_handler(CommandHandler("contact", contact_command))
    dp.add_handler(MessageHandler(Filters.text | Filters.voice, handle_message))
    dp.add_handler(CallbackQueryHandler(handle_payment))

    # Запуск бота
    updater.start_polling()
    logger.info('Бот запущен')
    updater.idle()

if __name__ == '__main__':
    main()
