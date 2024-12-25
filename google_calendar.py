from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pytz

class GoogleCalendar:
    def __init__(self, credentials):
        self.service = build('calendar', 'v3', credentials=credentials)
        calendar = self.service.calendars().get(calendarId='primary').execute()
        self.timezone = calendar.get('timeZone', 'Asia/Bangkok')
        
        self.COLORS = {
            'completed': '2',  # Green (Sage)
            'overdue': '4',    # Red (Flamingo)
            'default': '1'     # Blue (Lavender)
        }

    def _get_event_color(self, todo):
        if todo.get('completed', False) is True:
            return self.COLORS['completed']

        due_date = todo.get('due_date')
        if due_date is None:
            return self.COLORS['default']

        now = datetime.now(pytz.timezone(self.timezone))
        
        if due_date.tzinfo is None:
            due_date = pytz.timezone(self.timezone).localize(due_date)
            
        if due_date < now:
            return self.COLORS['overdue']
            
        return self.COLORS['default']

    def _prepare_event_times(self, due_date):
        local_tz = pytz.timezone(self.timezone)
        
        if due_date is None:
            start_time = local_tz.localize(datetime.now())
        elif due_date.tzinfo is None:
            start_time = local_tz.localize(due_date)
        else:
            start_time = due_date.astimezone(local_tz)
            
        end_time = start_time + timedelta(hours=1)
        return start_time, end_time

    def update_event(self, event_id, todo):
        """
        Update a Google Calendar event, preserving existing data if not provided in todo
        """
        try:
            # Get existing event
            existing_event = self.service.events().get(
                calendarId='primary', 
                eventId=event_id
            ).execute()
            
            # Print debug information
            print(f"Existing event data: {existing_event}")
            print(f"Updating with todo data: {todo}")
            
            # Preserve existing title and description if not provided in todo
            title = todo.get('title') or existing_event.get('summary', 'Untitled Task')
            description = todo.get('description') or existing_event.get('description', '')
            
            # Get the due date, defaulting to existing event time if not provided
            due_date = todo.get('due_date')
            if due_date is None and 'start' in existing_event:
                # Parse existing event time
                start_str = existing_event['start'].get('dateTime')
                if start_str:
                    due_date = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            
            start_time, end_time = self._prepare_event_times(due_date)
            
            # Update event data
            updated_event = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': self.timezone,
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': self.timezone,
                },
                'colorId': self._get_event_color(todo),
                'reminders': existing_event.get('reminders', {'useDefault': True})
            }
            
            # Print debug information
            print(f"Updating event with data: {updated_event}")
            
            # Update the event
            result = self.service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=updated_event
            ).execute()
            
            print(f"Successfully updated event {event_id}")
            return True
            
        except Exception as e:
            print(f"Error updating Google Calendar event: {e}")
            print(f"Todo data: {todo}")
            return False

    def create_event(self, todo):
        """
        Create a Google Calendar event from a todo item
        """
        try:
            title = str(todo.get('title', 'Untitled Task')).strip()
            description = str(todo.get('description', '')).strip()
            
            start_time, end_time = self._prepare_event_times(todo.get('due_date'))
            
            event = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': self.timezone,
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': self.timezone,
                },
                'colorId': self._get_event_color(todo),
                'reminders': {
                    'useDefault': True
                }
            }
            
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            print(f"Created event with ID: {created_event['id']}")
            return created_event['id']
            
        except Exception as e:
            print(f"Error creating Google Calendar event: {e}")
            return None

    def delete_event(self, event_id):
        try:
            self.service.events().delete(calendarId='primary', eventId=event_id).execute()
            print(f"Successfully deleted event {event_id}")
            return True
        except Exception as e:
            print(f"Error deleting Google Calendar event: {e}")
            return False