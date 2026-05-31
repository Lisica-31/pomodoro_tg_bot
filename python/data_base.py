import sqlite3
from datetime import datetime


def init_db():
    with sqlite3.connect('pomodoro_sessions.db') as connection:
        cursor = connection.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS completed_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_name TEXT,
                series INTEGER,
                work_time INTEGER,
                relax_time INTEGER,
                long_relax_time INTEGER,
                status TEXT,
                completion_date TEXT,
                completed_series INTEGER,
                total_time_minutes INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                template_name TEXT,
                series INTEGER,
                work_time INTEGER,
                relax_time INTEGER,
                long_relax_time INTEGER,
                created_date TEXT
            )
        ''')
        
        connection.commit()


def save_completed_session(chat_id, user_name, session_settings, status, completed_series):
    with sqlite3.connect('pomodoro_sessions.db') as connection:
        cursor = connection.cursor()
        
        total_time = completed_series * session_settings['work_time']
        if completed_series == session_settings['series']:
            total_time += (completed_series - 1) * session_settings['relax_time'] + session_settings['long_relax_time']
        else:
            total_time += completed_series * session_settings['relax_time']
        
        cursor.execute('''
            INSERT INTO completed_sessions 
            (chat_id, user_name, series, work_time, relax_time, long_relax_time, 
            status, completion_date, completed_series, total_time_minutes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            chat_id, user_name, session_settings['series'], session_settings['work_time'],
            session_settings['relax_time'], session_settings['long_relax_time'],
            status, datetime.now().isoformat(), completed_series, total_time
        ))
        
        connection.commit()

def get_all_user_sessions(chat_id):
    with sqlite3.connect('pomodoro_sessions.db') as connection:
        cursor = connection.cursor()
        
        cursor.execute('''
            SELECT id, status, completion_date, series, work_time, relax_time, 
                long_relax_time, completed_series, total_time_minutes
            FROM completed_sessions
            WHERE chat_id = ?
            ORDER BY completion_date DESC
        ''', (chat_id,))
        
        sessions = cursor.fetchall()
        return sessions

def delete_session_from_archive(session_id, chat_id):
    with sqlite3.connect('pomodoro_sessions.db') as connection:
        cursor = connection.cursor()
        
        cursor.execute('''
            DELETE FROM completed_sessions
            WHERE id = ? AND chat_id = ?
        ''', (session_id, chat_id))
        
        deleted = cursor.rowcount > 0
        connection.commit()
        return deleted



def save_session_template(chat_id, template_name, session_settings):
    with sqlite3.connect('pomodoro_sessions.db') as connection:
        cursor = connection.cursor()
        cursor.execute('''
            INSERT INTO session_templates 
            (chat_id, template_name, series, work_time, relax_time, long_relax_time, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            chat_id, template_name, session_settings['series'], session_settings['work_time'],
            session_settings['relax_time'], session_settings['long_relax_time'], datetime.now().isoformat()
        ))
        
        connection.commit()

def get_unique_templates(chat_id):
    with sqlite3.connect('pomodoro_sessions.db') as connection:
        cursor = connection.cursor()
        
        cursor.execute('''
            SELECT DISTINCT series, work_time, relax_time, long_relax_time, 
                MIN(id) as template_id, 
                (SELECT template_name FROM session_templates t2 
                    WHERE t2.series = t1.series AND t2.work_time = t1.work_time 
                    AND t2.relax_time = t1.relax_time AND t2.long_relax_time = t1.long_relax_time 
                    LIMIT 1) as template_name
            FROM session_templates t1
            WHERE chat_id = ?
            GROUP BY series, work_time, relax_time, long_relax_time
            ORDER BY MIN(created_date) DESC
        ''', (chat_id,))
        
        templates = cursor.fetchall()
        return templates

def get_template_by_id(template_id, chat_id):
    with sqlite3.connect('pomodoro_sessions.db') as connection:
        cursor = connection.cursor()
        
        cursor.execute('''
            SELECT id, template_name, series, work_time, relax_time, long_relax_time, created_date
            FROM session_templates
            WHERE id = ? AND chat_id = ?
            ORDER BY id DESC
            LIMIT 1
        ''', (template_id, chat_id))
        
        template = cursor.fetchone()
        return template


def delete_template(template_id, chat_id):
    with sqlite3.connect('pomodoro_sessions.db') as connection:
        cursor = connection.cursor()
        
        cursor.execute('''
            DELETE FROM session_templates
            WHERE id = ? AND chat_id = ?
        ''', (template_id, chat_id))
        
        deleted = cursor.rowcount > 0
        connection.commit()
        return deleted
