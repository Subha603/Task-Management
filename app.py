from flask import Flask, request, jsonify, redirect, url_for, session
from db_config import init_db_pools, get_db_connection, release_connection
from google_calendar import GoogleCalendar
import psycopg2.extras
import os
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from datetime import datetime
from flask import render_template
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config.from_object('config.Config')

# Initialize database pools after app creation
with app.app_context():
    init_db_pools()

# Google OAuth2 configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']
CLIENT_SECRETS_FILE = '' 



@app.route('/')
def index():
    # If the user is authenticated, show the main page
    if 'credentials' in session:
        return render_template('index.html', authenticated=True)
    # Otherwise, redirect to the login page
    return redirect(url_for('login_page'))

@app.route('/login-page')
def login_page():
    # Render the standalone login page
    return render_template('login.html')

@app.route('/login')
def login():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    try:
        state = session['state']
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            state=state,
            redirect_uri=url_for('oauth2callback', _external=True)
        )
        
        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)
        
        credentials = flow.credentials
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        return redirect(url_for('index'))
    except Exception as e:
        print(f"OAuth callback error: {e}")
        return redirect(url_for('login_page'))
    
@app.route('/logout')
def logout():
    if 'credentials' in session:
        del session['credentials']
    return redirect(url_for('login_page'))

@app.route('/auth/status')
def auth_status():
    if 'credentials' not in session:
        return jsonify({'authenticated': False})
    return jsonify({'authenticated': True})

@app.route('/todos', methods=['GET'])
def get_todos():
    if 'credentials' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT id, title, description, due_date, completed, google_event_id 
                FROM todos 
                WHERE user_id = %s
                """, (session['credentials']['token'],))
            todos = cur.fetchall()
            
            return jsonify([{
                'id': todo['id'],
                'title': todo['title'],
                'description': todo['description'],
                'due_date': todo['due_date'].isoformat(),
                'completed': todo['completed']
            } for todo in todos])
    finally:
        release_connection(conn)

@app.route('/todos', methods=['POST'])
def create_todo():
    if 'credentials' not in session:
        return redirect(url_for('login'))
    
    data = request.json
    conn = get_db_connection()
    try:
        # Create Google Calendar event
        credentials = Credentials(**session['credentials'])
        calendar = GoogleCalendar(credentials)
        
        todo = {
            'title': data['title'],
            'description': data.get('description', ''),
            'due_date': datetime.fromisoformat(data['due_date']),
            'user_id': session['credentials']['token']
        }
        
        event_id = calendar.create_event(todo)
        
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                INSERT INTO todos (title, description, due_date, user_id, google_event_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, title, description, due_date, completed
                """, (
                    todo['title'],
                    todo['description'],
                    todo['due_date'],
                    todo['user_id'],
                    event_id
                ))
            conn.commit()
            new_todo = cur.fetchone()
            
            return jsonify({
                'id': new_todo['id'],
                'title': new_todo['title'],
                'description': new_todo['description'],
                'due_date': new_todo['due_date'].isoformat(),
                'completed': new_todo['completed']
            }), 201
    finally:
        release_connection(conn)

@app.route('/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    if 'credentials' not in session:
        return redirect(url_for('login'))
    
    data = request.json
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # First get the current todo and its Google Calendar event ID
            cur.execute("""
                SELECT id, google_event_id 
                FROM todos 
                WHERE id = %s AND user_id = %s
                """, (todo_id, session['credentials']['token']))
            current_todo = cur.fetchone()
            
            if current_todo is None:
                return jsonify({'error': 'Todo not found'}), 404

            try:
                # Update Google Calendar event if it exists
                if current_todo['google_event_id']:
                    credentials = Credentials(**session['credentials'])
                    calendar = GoogleCalendar(credentials)
                    calendar.update_event(
                        current_todo['google_event_id'],
                        {
                            'title': data.get('title'),
                            'description': data.get('description'),
                            'due_date': datetime.fromisoformat(data['due_date']) if 'due_date' in data else None
                        }
                    )
            except Exception as e:
                print(f"Google Calendar update error: {e}")
                return jsonify({'error': 'Failed to update calendar event'}), 500

            # Update database
            try:
                cur.execute("""
                    UPDATE todos 
                    SET title = COALESCE(%s, title),
                        description = COALESCE(%s, description),
                        completed = COALESCE(%s, completed),
                        due_date = COALESCE(%s, due_date)
                    WHERE id = %s AND user_id = %s
                    RETURNING id, title, description, due_date, completed
                    """, (
                        data.get('title'),
                        data.get('description'),
                        data.get('completed'),
                        datetime.fromisoformat(data['due_date']) if 'due_date' in data else None,
                        todo_id,
                        session['credentials']['token']
                    ))
                conn.commit()
                updated_todo = cur.fetchone()
                
                return jsonify({
                    'id': updated_todo['id'],
                    'title': updated_todo['title'],
                    'description': updated_todo['description'],
                    'due_date': updated_todo['due_date'].isoformat(),
                    'completed': updated_todo['completed']
                })
            except Exception as e:
                conn.rollback()
                print(f"Database update error: {e}")
                return jsonify({'error': 'Failed to update todo'}), 500
    finally:
        release_connection(conn)

@app.route('/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    if 'credentials' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # First get the Google Calendar event ID
            cur.execute("SELECT google_event_id FROM todos WHERE id = %s AND user_id = %s",
                       (todo_id, session['credentials']['token']))
            todo = cur.fetchone()
            
            if todo is None:
                return jsonify({'error': 'Todo not found'}), 404
            
            # Delete from Google Calendar
            if todo['google_event_id']:
                try:
                    credentials = Credentials(**session['credentials'])
                    calendar = GoogleCalendar(credentials)
                    calendar.delete_event(todo['google_event_id'])
                except Exception as e:
                    print(f"Google Calendar delete error: {e}")
                    return jsonify({'error': 'Failed to delete calendar event'}), 500
            
            # Delete from database
            try:
                cur.execute("DELETE FROM todos WHERE id = %s AND user_id = %s",
                           (todo_id, session['credentials']['token']))
                conn.commit()
                return '', 204
            except Exception as e:
                conn.rollback()
                print(f"Database delete error: {e}")
                return jsonify({'error': 'Failed to delete todo'}), 500
    finally:
        release_connection(conn)

def init_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # First, try to alter the existing column if the table exists
            try:
                cur.execute("""
                    ALTER TABLE todos 
                    ALTER COLUMN user_id TYPE VARCHAR(500);
                """)
                conn.commit()
            except Exception as e:
                # If table doesn't exist, this will fail, which is fine
                conn.rollback()
            
            # Create table if it doesn't exist with new column size
            cur.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(100) NOT NULL,
                    description VARCHAR(200),
                    due_date TIMESTAMP NOT NULL,
                    completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    google_event_id VARCHAR(100),
                    user_id VARCHAR(500) NOT NULL
                )
            """)
            conn.commit()
    finally:
        release_connection(conn)

if __name__ == '__main__':
    # Make sure to set a secret key for session management
    app.secret_key = os.getenv('SECRET_KEY', '123')
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Only for development
    with app.app_context():
        init_db()
    app.run(debug=True, port=5000)