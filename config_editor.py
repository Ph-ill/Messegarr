import os
import logging
from flask import Flask, render_template, request, jsonify, redirect
from dotenv import load_dotenv, set_key
from pathlib import Path
import subprocess
import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# Configure logging to output to console at DEBUG level.
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)

# Global scheduler instance
scheduler = BackgroundScheduler()

# Load .env files
config_env_file = Path('config.env')
credentials_env_file = Path('credentials.env')
load_dotenv(dotenv_path=config_env_file)
load_dotenv(dotenv_path=credentials_env_file)

def save_to_env_file(env_file, data):
    """ Save updated data to the specified .env file, excluding keys with empty values. """
    updated_lines = []
    for key, value in data.items():
        if value:
            updated_lines.append(f"{key}={value}\n")
    with open(env_file, 'w') as file:
        file.writelines(updated_lines)

def run_main_script():
    """Run main.py to pull data, compose messages, and send them."""
    logging.info(f"Running main.py at {datetime.datetime.now()}")
    result = subprocess.run(['bin/python', 'main.py'], capture_output=True, text=True)
    logging.info(f"main.py executed. Return code: {result.returncode}")
    logging.debug(f"Output from main.py: {result.stdout}")
    if result.stderr:
        logging.error(f"Errors from main.py: {result.stderr}")

def update_scheduler():
    """Update (or initialize) the scheduler job based on current .env settings."""
    schedule_time = os.getenv("SCHEDULE_TIME", "08:00")
    schedule_days = os.getenv("SCHEDULE_DAYS", "mon,tue,wed,thu,fri")
    logging.debug(f"Updating scheduler with time: {schedule_time}, days: {schedule_days}")
    try:
        hour, minute = map(int, schedule_time.split(":"))
    except ValueError:
        logging.error("Invalid SCHEDULE_TIME format. Using default 08:00.")
        hour, minute = 8, 0

    # Remove existing job if it exists
    try:
        scheduler.remove_job('main_script_job')
        logging.debug("Existing job 'main_script_job' removed.")
    except Exception as e:
        logging.debug("No existing job to remove.")

    scheduler.add_job(
        run_main_script,
        trigger='cron',
        day_of_week=schedule_days,
        hour=hour,
        minute=minute,
        id='main_script_job',
        replace_existing=True
    )
    logging.info(f"Scheduler updated: main.py will run on {schedule_days} at {schedule_time}.")

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save':
            num_recipients = request.form['NUM_RECIPIENTS']
            num_recipients = int(num_recipients) if num_recipients else 1

            # Retrieve scheduling fields
            schedule_time = request.form.get('SCHEDULE_TIME', '08:00')
            schedule_days_list = request.form.getlist('SCHEDULE_DAYS')
            schedule_days_str = ','.join(schedule_days_list)

            # Save config.env values including scheduling settings
            config_values = {
                'SONARR_HOST': request.form['SONARR_HOST'],
                'RADARR_HOST': request.form['RADARR_HOST'],
                'NUM_RECIPIENTS': str(num_recipients),
                'WHATSAPP_ENABLED': 'true' if 'WHATSAPP_ENABLED' in request.form else 'false',
                'TELEGRAM_ENABLED': 'true' if 'TELEGRAM_ENABLED' in request.form else 'false',
                'AI_ENABLED': 'true' if 'AI_ENABLED' in request.form else 'false',
                'SCHEDULE_TIME': schedule_time,
                'SCHEDULE_DAYS': schedule_days_str
            }
            save_to_env_file(config_env_file, config_values)

            # Save credentials.env values
            credentials_values = {
                'SONARR_API_KEY': request.form['SONARR_API_KEY'],
                'RADARR_API_KEY': request.form['RADARR_API_KEY'],
                'MISTRAL_API_KEY': request.form['MISTRAL_API_KEY'],
                'OMDB_API_KEY': request.form['OMDB_API_KEY'],
                'TELEGRAM_TOKEN': request.form['TELEGRAM_TOKEN']
            }
            for i in range(1, num_recipients + 1):
                phone_number = request.form.get(f'PHONE_NUMBER_{i}', '')
                phone_number_api_key = request.form.get(f'PHONE_NUMBER_{i}_API_KEY', '')
                telegram_chat_id = request.form.get(f'TELEGRAM_CHAT_ID_{i}', '')
                if phone_number:
                    credentials_values[f'PHONE_NUMBER_{i}'] = phone_number
                if phone_number_api_key:
                    credentials_values[f'PHONE_NUMBER_{i}_API_KEY'] = phone_number_api_key
                if telegram_chat_id:
                    credentials_values[f'TELEGRAM_CHAT_ID_{i}'] = telegram_chat_id
            save_to_env_file(credentials_env_file, credentials_values)

            # Reload .env files after saving
            load_dotenv(dotenv_path=config_env_file, override=True)
            load_dotenv(dotenv_path=credentials_env_file, override=True)
            logging.debug("Configuration saved and .env files reloaded.")

            # Update scheduler with new settings
            update_scheduler()

            return redirect('/')

        elif action == 'run_script':
            # Run main.py and return JSON feedback for test message
            try:
                result = subprocess.run(['bin/python', 'main.py'], capture_output=True, text=True)
                status = 'success' if result.returncode == 0 else 'error'
                message = 'Test message sent successfully!' if result.returncode == 0 else 'Script execution failed!'
                logging.debug(f"Manual run_script action executed. Output: {result.stdout}")
            except Exception as e:
                status = 'error'
                message = str(e)
                logging.error(f"Error running main.py: {e}")
            return jsonify({'status': status, 'message': message})

    # Load existing values for the form
    load_dotenv(dotenv_path=config_env_file)
    load_dotenv(dotenv_path=credentials_env_file)
    config_data = {
        'SONARR_HOST': os.getenv('SONARR_HOST', ''),
        'RADARR_HOST': os.getenv('RADARR_HOST', ''),
        'NUM_RECIPIENTS': os.getenv('NUM_RECIPIENTS', '1'),
        'WHATSAPP_ENABLED': os.getenv('WHATSAPP_ENABLED', 'false'),
        'TELEGRAM_ENABLED': os.getenv('TELEGRAM_ENABLED', 'false'),
        'AI_ENABLED': os.getenv('AI_ENABLED', 'false'),
        'SCHEDULE_TIME': os.getenv('SCHEDULE_TIME', '08:00'),
        'SCHEDULE_DAYS': os.getenv('SCHEDULE_DAYS', 'mon,tue,wed,thu,fri')
    }
    credentials_data = {
        'SONARR_API_KEY': os.getenv('SONARR_API_KEY', ''),
        'RADARR_API_KEY': os.getenv('RADARR_API_KEY', ''),
        'MISTRAL_API_KEY': os.getenv('MISTRAL_API_KEY', ''),
        'OMDB_API_KEY': os.getenv('OMDB_API_KEY', ''),
        'TELEGRAM_TOKEN': os.getenv('TELEGRAM_TOKEN', '')
    }
    num_recipients = int(config_data['NUM_RECIPIENTS']) if config_data['NUM_RECIPIENTS'] else 1
    for i in range(1, num_recipients + 1):
        credentials_data[f'PHONE_NUMBER_{i}'] = os.getenv(f'PHONE_NUMBER_{i}', '')
        credentials_data[f'PHONE_NUMBER_{i}_API_KEY'] = os.getenv(f'PHONE_NUMBER_{i}_API_KEY', '')
        credentials_data[f'TELEGRAM_CHAT_ID_{i}'] = os.getenv(f'TELEGRAM_CHAT_ID_{i}', '')
    return render_template('index.html', config_data=config_data, credentials_data=credentials_data, num_recipients=num_recipients)

def init_scheduler():
    """Initialize the scheduler to run main.py based on scheduling settings."""
    schedule_time = os.getenv("SCHEDULE_TIME", "08:00")
    schedule_days = os.getenv("SCHEDULE_DAYS", "mon,tue,wed,thu,fri")
    logging.debug(f"Initializing scheduler with time: {schedule_time}, days: {schedule_days}")
    try:
        hour, minute = map(int, schedule_time.split(":"))
    except ValueError:
        logging.error("Invalid SCHEDULE_TIME format. Using default 08:00.")
        hour, minute = 8, 0

    scheduler.add_job(
        run_main_script,
        trigger='cron',
        day_of_week=schedule_days,
        hour=hour,
        minute=minute,
        id='main_script_job',
        replace_existing=True
    )
    scheduler.start()
    logging.info(f"Scheduler started: main.py will run on {schedule_days} at {schedule_time}.")

if __name__ == '__main__':
    port = 5000
    logging.info(f"Server running at http://{os.getenv('LOCAL_IP', '127.0.0.1')}:{port}")
    init_scheduler()
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
