import sqlite3
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import os
from pathlib import Path

db_path = str(Path(__file__).resolve().parent.parent / "data" / "reminders.db")
print(db_path)
class ReminderHelper:
    def __init__(self, db_path=db_path):
            print("initialising")
            self.db_path = db_path
            print(self.db_path)
            self._init_database()
    
    def _init_database(self):
        """Create database and table if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    relationship TEXT,
                    date TEXT NOT NULL,
                    next_occurrance NOT NULL,
                    event_type TEXT NOT NULL,
                    repeatable TEXT DEFAULT 'one-time',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def _parse_natural_language(self, text: str) -> Dict[str, str]:
        """
        Parse natural language input into structured data.
        Supports formats like:
        - "Rozian, wife, 1991/12/28, birthday, yearly"
        - "Remind me about Rozian's birthday on 1991/12/28 (wife, yearly)"
        - "birthday for Rozian (wife) on 1991/12/28 yearly"
        """
        # Remove leading command
        text = re.sub(r'^/reminder\s+', '', text, flags=re.IGNORECASE)
        
        parsed = {
            'name': None,
            'relationship': None,
            'date': None,
            'event_type': None,
            'repeatable': 'one-time',
            'next_occurrance': None
        }
        
        # Try comma-separated format first
        if ',' in text:
            parts = [p.strip() for p in text.split(',')]
            if len(parts) >= 3:
                # Try to identify each part
                for part in parts:
                    part_lower = part.lower()
                    # Check if it's a date
                    if re.search(r'\d{4}[/-]\d{1,2}[/-]\d{1,2}', part):
                        parsed['date'] = self._normalize_date(part)
                        # The next occurance of an event was never being returined because the SQL query only retrieved the first occurrance date. //
                        # This creates a field to remember the next occurrance of an event.
                        current_date_array = parsed['date'].split("-")
                        
                        current_year = datetime.now().year
                        
                        next_occurrance = current_date_array
                        next_occurrance[0] = str(current_year)
                        next_occurrance_text =  ("-").join(next_occurrance)
                        parsed['next_occurrance'] = next_occurrance_text

                    # Check if it's a repeatable keyword
                    elif part_lower in ['yearly', 'monthly', 'weekly', 'daily', 'one-time']:
                        parsed['repeatable'] = part_lower
                    # Check if it's a relationship (common relationship words)
                    elif part_lower in ['wife', 'husband', 'partner', 'son', 'daughter', 'mother', 'father', 'friend', 'brother', 'sister', 'neice', 'nephew']:
                        parsed['relationship'] = part
                    # If event_type not set, treat as event_type
                    elif part_lower in ['birthday', 'anniversary', 'event', 'task', 'reminder']:
                        parsed['event_type'] = part
                    # Otherwise treat as name
                    elif parsed['name'] is None:
                        parsed['name'] = part
        
        # If comma parsing failed, try natural language patterns
        if parsed['name'] is None:
            parsed = self._parse_natural_patterns(text)
        
        # Validate required fields
        if parsed['name'] is None:
            parsed['name'] = "Unknown"
        if parsed['date'] is None:
            raise ValueError("Date not found in input")
        if parsed['event_type'] is None:
            parsed['event_type'] = "Reminder"
        
        return parsed
    
    def _parse_natural_patterns(self, text: str) -> Dict[str, str]:
        """Parse using regex patterns for natural language"""
        parsed = {'name': None, 'relationship': None, 'date': None, 
                  'event_type': None, 'repeatable': 'one-time', 'next_occurrance' :None}
        
        # Extract date (supports YYYY-MM-DD, YYYY/MM/DD, DD/MM/YYYY, MM/DD/YYYY)
        date_match = re.search(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})', text)
        if date_match:
            parsed['date'] = self._normalize_date(date_match.group())
            text = text.replace(date_match.group(), '')
        
        # Extract repeatable
        repeat_match = re.search(r'\b(yearly|monthly|weekly|daily|one-time)\b', text, re.IGNORECASE)
        if repeat_match:
            parsed['repeatable'] = repeat_match.group().lower()
            text = text.replace(repeat_match.group(), '')
        
        # Extract relationship (common patterns: "for X", "of X", "(X)", "X's")
        rel_patterns = [
            r'\b(?:for|of|about)\s+(\w+)\s*$',  # "for wife"
            r'\(([^)]+)\)',  # "(wife)"
            r"(\w+)'s",  # "wife's"
        ]
        for pattern in rel_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                potential_rel = match.group(1)
                if potential_rel.lower() in ['wife', 'husband', 'partner', 'son', 'daughter', 
                                            'mother', 'father', 'friend', 'brother', 'sister', 'neice', 'nephew']:
                    parsed['relationship'] = potential_rel
                    text = text.replace(match.group(0), '')
                    break
        
        # Extract event type (usually a single word before "for" or after "about")
        event_match = re.search(r'\b(\w+)\s+(?:for|of|about|on)\b', text, re.IGNORECASE)
        if event_match:
            parsed['event_type'] = event_match.group(1)
            text = text.replace(event_match.group(0), '')
        
        # Extract name (remaining text)
        name_text = re.sub(r'\b(on|for|of|about|the|a|an)\b', '', text, flags=re.IGNORECASE)
        name_text = ' '.join(name_text.split())
        if name_text:
            parsed['name'] = name_text.strip()


        return parsed
    
    def _normalize_date(self, date_str: str) -> str:
        """Convert various date formats to YYYY-MM-DD"""
        date_str = date_str.strip()
        # Try different formats
        formats = [
            '%Y/%m/%d', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y',
            '%d-%m-%Y', '%m-%d-%Y'
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        raise ValueError(f"Unable to parse date: {date_str}")
    
    def add_reminder(self, input_text: str) -> str:
        """
        Main function to add a reminder from natural language input.
        Returns a success or error message.
        """
        try:
            # Parse the input
            parsed = self._parse_natural_language(input_text)
            
            # Validate date
            try:
                datetime.strptime(parsed['date'], '%Y-%m-%d')
            except ValueError:
                return f"❌ Invalid date format. Please use YYYY-MM-DD or YYYY/MM/DD"
            
            # Insert into database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO reminders (name, relationship, date, event_type, repeatable, next_occurrance)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    parsed['name'],
                    parsed['relationship'],
                    parsed['date'],
                    parsed['event_type'],
                    parsed['repeatable'],
                    parsed['next_occurrance']
                ))
                conn.commit()
                reminder_id = cursor.lastrowid
            
            # Return success message
            repeat_msg = f" (repeats {parsed['repeatable']})" if parsed['repeatable'] != 'one-time' else ""
            rel_msg = f" ({parsed['relationship']})" if parsed['relationship'] else ""
            return (f"✅ Reminder added successfully! (ID: {reminder_id})\n"
                   f"📌 {parsed['name']}{rel_msg} - {parsed['event_type']}\n"
                   f"📅 Date: {parsed['date']}{repeat_msg}")
            
        except ValueError as e:
            return f"❌ Error: {str(e)}\n\n📝 Expected format:\n" \
                   f"  /reminder Name, Relationship, YYYY-MM-DD, Event, yearly\n" \
                   f"  /reminder birthday for John (friend) on 2024-12-25 yearly\n" \
                   f"  /reminder John's anniversary 2024-06-15"
        except Exception as e:
            print(e)
            return f"❌ Unexpected error: {str(e)}"

class GetReminders:
    def __init__(self, db_path=db_path):
        self.db_path = db_path
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Check if database exists and has the reminders table"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='reminders'
                """)
                if not cursor.fetchone():
                    raise FileNotFoundError("Reminders table doesn't exist. Please add some reminders first.")
        except sqlite3.Error:
            raise FileNotFoundError(f"Database '{self.db_path}' not found or corrupted.")
    
    def _parse_repeatable(self, repeatable: str, base_date: str) -> List[datetime]:
        """
        Calculate next occurrence dates based on repeatable pattern
        Returns list of upcoming dates (next 5 occurrences max)
        """
        base = datetime.strptime(base_date, '%Y-%m-%d')
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        occurrences = []
        
        if repeatable == 'one-time':
            if base >= now:
                occurrences.append(base)
            return occurrences
        
        # For yearly, monthly, weekly, daily
        current = base
        max_attempts = 100  # Prevent infinite loops
        attempts = 0
        
        while len(occurrences) < 5 and attempts < max_attempts:
            attempts += 1
            
            # Skip if date is in the past (but not the initial date we're checking)
            if current < now and current != base:
                pass
            elif current >= now:
                occurrences.append(current)
            
            # Move to next occurrence
            if repeatable == 'yearly':
                try:
                    current = current.replace(year=current.year + 1)
                except ValueError:  # Handle Feb 29
                    current = current.replace(year=current.year + 1, day=28)
            elif repeatable == 'monthly':
                # Handle month rollover
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    try:
                        current = current.replace(month=current.month + 1)
                    except ValueError:
                        # Handle months with different days (e.g., Jan 31 -> Feb 28)
                        current = current.replace(month=current.month + 1, day=28)
            elif repeatable == 'weekly':
                current = current + timedelta(days=7)
            elif repeatable == 'daily':
                current = current + timedelta(days=1)
            else:
                break
        
        return occurrences
    
    def _format_markdown(self, reminders: List[Dict]) -> str:
        """
        Format reminders as Markdown with emojis and proper structure
        """
        if not reminders:
            return "🎉 *No upcoming reminders found!*"
        
        # Group by date
        grouped = {}
        for reminder in reminders:
            date_key = reminder['date']
            if date_key not in grouped:
                grouped[date_key] = []
            grouped[date_key].append(reminder)
        
        # Sort dates
        sorted_dates = sorted(grouped.keys())
        
        # Build markdown
        lines = []
        lines.append("📅 *UPCOMING REMINDERS*\n")
        
        for date_str in sorted_dates:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            date_display = date_obj.strftime('%A, %B %d, %Y')
            
            # Calculate days until
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            days_until = (date_obj - today).days
            
            if days_until == 0:
                date_header = f"🔴 *TODAY* - {date_display}"
            elif days_until == 1:
                date_header = f"🟡 *TOMORROW* - {date_display}"
            elif days_until <= 7:
                date_header = f"🟢 *{days_until} days* - {date_display}"
            else:
                date_header = f"📌 *{date_display}*"
            
            lines.append(date_header)
            lines.append("")
            
            for reminder in grouped[date_str]:
                # Build each reminder line
                name = reminder['name']
                relationship = reminder['relationship']
                event_type = reminder['event_type']
                repeatable = reminder['repeatable']
                
                # Create relationship string
                rel_str = f" (*{relationship}*)" if relationship else ""
                
                # Create repeat indicator
                repeat_icon = {
                    'yearly': '🔄',
                    'monthly': '📆',
                    'weekly': '📅',
                    'daily': '⏰',
                    'one-time': '📍'
                }.get(repeatable, '📍')
                
                repeat_str = f" {repeat_icon} *{repeatable}*" if repeatable != 'one-time' else ""
                
                # Main line
                line = f"• *{event_type}* for {name}{rel_str}{repeat_str}"
                lines.append(line)
            
            lines.append("")  # Empty line between dates
        
        # Add footer with total count
        total = len(reminders)
        lines.append(f"---\n📊 *Total: {total} reminder{'s' if total > 1 else ''}*")
        
        return "\n".join(lines)
    
    def get_upcoming(
        self, 
        days_ahead: int = 30,
        limit: Optional[int] = None,
        include_repeatables: bool = True
    ) -> str:
        """
        Get upcoming reminders and return as Markdown
        
        Args:
            days_ahead: How many days ahead to look (default: 30)
            limit: Maximum number of reminders to return (default: None = unlimited)
            include_repeatables: Include repeating reminders (default: True)
        
        Returns:
            Markdown formatted string
        """
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            future_date = today + timedelta(days=days_ahead)
            future_str = future_date.strftime('%Y-%m-%d')
            today_str = today.strftime('%Y-%m-%d')
            
            reminders = []
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get all reminders (including repeatable ones)
                cursor.execute("""
                    SELECT * FROM reminders 
                    WHERE next_occurrance >= ?
                    ORDER BY date ASC, id ASC
                """, (today_str,))
                
                rows = cursor.fetchall()
                
                for row in rows:
                    reminder = dict(row)
                    repeatable = reminder['repeatable']
                    
                    if repeatable == 'one-time':
                        # Check if it's within our time window
                        if reminder['date'] <= future_str:
                            reminders.append(reminder)
                    elif include_repeatables:
                        # Calculate future occurrences
                        occurrences = self._parse_repeatable(
                            repeatable, 
                            reminder['date']
                        )
                        
                        # Filter occurrences within time window
                        for occ_date in occurrences:
                            if occ_date <= future_date:
                                # Create a copy of the reminder with the new date
                                occ_reminder = reminder.copy()
                                occ_reminder['date'] = occ_date.strftime('%Y-%m-%d')
                                reminders.append(occ_reminder)
                        
                        # Also include the original if it hasn't passed
                        orig_date = datetime.strptime(reminder['date'], '%Y-%m-%d')
                        if orig_date >= today and orig_date <= future_date:
                            # Check if we already added it via occurrences
                            if not any(r['date'] == reminder['date'] and 
                                     r['id'] == reminder['id'] for r in reminders):
                                reminders.append(reminder)
            
            # Remove duplicates (same reminder id and same date)
            seen = set()
            unique_reminders = []
            for r in reminders:
                key = (r['id'], r['date'])
                if key not in seen:
                    seen.add(key)
                    unique_reminders.append(r)
            
            # Sort by date
            unique_reminders.sort(key=lambda x: x['date'])
            
            # Apply limit
            if limit and len(unique_reminders) > limit:
                unique_reminders = unique_reminders[:limit]
            
            # Format and return
            return self._format_markdown(unique_reminders)
            
        except FileNotFoundError as e:
            return f"⚠️ *Error:* {str(e)}\n\nPlease add some reminders first using /reminder"
        except Exception as e:
            return f"❌ *Error retrieving reminders:* {str(e)}"
    
    def get_today(self) -> str:
        """Get only today's reminders"""
        return self.get_upcoming(days_ahead=0)
    
    def get_week(self) -> str:
        """Get reminders for the next 7 days"""
        return self.get_upcoming(days_ahead=7)
    
    def get_month(self) -> str:
        """Get reminders for the next 30 days"""
        return self.get_upcoming(days_ahead=30)


# ============= TELEGRAM BOT INTEGRATION =============

def create_telegram_get_handler(get_reminders_instance):
    """Create a handler for getting reminders in Telegram"""
    async def handle_get_reminders(update, context):
        # Parse optional arguments
        args = context.args if context.args else []
        
        # Default to 30 days if no args
        days = 30
        limit = None
        
        for arg in args:
            if arg.isdigit():
                days = int(arg)
            elif arg.startswith('limit='):
                try:
                    limit = int(arg.split('=')[1])
                except:
                    pass
        
        # Get reminders
        result = get_reminders_instance.get_upcoming(days_ahead=days, limit=limit)
        
        # Send as Markdown
        await update.message.reply_text(result, parse_mode='Markdown')
    
    return handle_get_reminders

def create_telegram_today_handler(get_reminders_instance):
    """Handler for today's reminders"""
    async def handle_today(update, context):
        result = get_reminders_instance.get_today()
        await update.message.reply_text(result, parse_mode='Markdown')
    return handle_today

if __name__ == "__main__":
    # ============= EXAMPLE USAGE =============

    # Create instance
    helper = ReminderHelper()
    # Test with various inputs
    test_inputs = [
        "/reminder birthday, wife, 1991/12/28, Rozian, yearly",
        "/reminder birthday for John (friend) on 2024-12-25",
        "/reminder John's anniversary 2024-06-15 yearly",
        "/reminder Mary mother 2020/05/10 mothers-day one-time",
        "/reminder invalid input",  # This will show error
    ]

    print("=" * 60)
    print("TESTING REMINDER HELPER")
    print("=" * 60)

    for test in test_inputs:
        print(f"\n📝 Input: {test}")
        print(helper.add_reminder(test))

    # Optional: View all reminders in database
    print("\n" + "=" * 60)
    print("ALL REMINDERS IN DATABASE:")
    print("=" * 60)

    with sqlite3.connect(str(Path(__file__).resolve().parent.parent / "data" / "reminders.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reminders ORDER BY id")
        rows = cursor.fetchall()
        for row in rows:
            print(f"ID: {row[0]}, Name: {row[1]}, Date: {row[3]}, Event: {row[4]}, Repeat: {row[5]}")