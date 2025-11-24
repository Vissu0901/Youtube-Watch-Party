import sqlite3
import time

DB_NAME = 'youtube_watch.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Rooms table
    c.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY,
            host_id TEXT NOT NULL,
            host_sid TEXT,
            video_id TEXT,
            is_playing INTEGER DEFAULT 0,
            current_time REAL DEFAULT 0,
            created_at REAL
        )
    ''')
    
    # Approved users table (persists approvals)
    c.execute('''
        CREATE TABLE IF NOT EXISTS room_permissions (
            room_id TEXT,
            user_id TEXT,
            user_name TEXT,
            is_approved INTEGER DEFAULT 0,
            PRIMARY KEY (room_id, user_id),
            FOREIGN KEY (room_id) REFERENCES rooms (room_id) ON DELETE CASCADE
        )
    ''')
    
    # Pending requests (transient, but good to have in DB for management)
    c.execute('''
        CREATE TABLE IF NOT EXISTS join_requests (
            room_id TEXT,
            user_id TEXT,
            user_name TEXT,
            sid TEXT,
            created_at REAL,
            PRIMARY KEY (room_id, user_id),
            FOREIGN KEY (room_id) REFERENCES rooms (room_id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

# Room Operations
def create_room(room_id, host_id, host_sid, user_name):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO rooms (room_id, host_id, host_sid, created_at) VALUES (?, ?, ?, ?)',
                  (room_id, host_id, host_sid, time.time()))
        # Host is automatically approved
        c.execute('INSERT INTO room_permissions (room_id, user_id, user_name, is_approved) VALUES (?, ?, ?, 1)',
                  (room_id, host_id, user_name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_room(room_id):
    conn = get_db_connection()
    room = conn.execute('SELECT * FROM rooms WHERE room_id = ?', (room_id,)).fetchone()
    conn.close()
    return dict(room) if room else None

def update_room_host_sid(room_id, new_sid):
    conn = get_db_connection()
    conn.execute('UPDATE rooms SET host_sid = ? WHERE room_id = ?', (new_sid, room_id))
    conn.commit()
    conn.close()

def update_room_state(room_id, video_id=None, is_playing=None, current_time=None):
    conn = get_db_connection()
    query = 'UPDATE rooms SET '
    params = []
    updates = []
    
    if video_id is not None:
        updates.append('video_id = ?')
        params.append(video_id)
    if is_playing is not None:
        updates.append('is_playing = ?')
        params.append(1 if is_playing else 0)
    if current_time is not None:
        updates.append('current_time = ?')
        params.append(current_time)
        
    if not updates:
        conn.close()
        return
        
    query += ', '.join(updates) + ' WHERE room_id = ?'
    params.append(room_id)
    
    conn.execute(query, params)
    conn.commit()
    conn.close()

def delete_room(room_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM rooms WHERE room_id = ?', (room_id,))
    conn.execute('DELETE FROM room_permissions WHERE room_id = ?', (room_id,))
    conn.execute('DELETE FROM join_requests WHERE room_id = ?', (room_id,))
    conn.commit()
    conn.close()

# Permission/Request Operations
def is_user_approved(room_id, user_id):
    conn = get_db_connection()
    res = conn.execute('SELECT is_approved FROM room_permissions WHERE room_id = ? AND user_id = ?', 
                       (room_id, user_id)).fetchone()
    conn.close()
    return res and res['is_approved'] == 1

def add_join_request(room_id, user_id, user_name, sid):
    conn = get_db_connection()
    try:
        conn.execute('INSERT OR REPLACE INTO join_requests (room_id, user_id, user_name, sid, created_at) VALUES (?, ?, ?, ?, ?)',
                     (room_id, user_id, user_name, sid, time.time()))
        conn.commit()
    except Exception as e:
        print(f"Error adding join request: {e}")
    finally:
        conn.close()

def get_pending_requests(room_id):
    conn = get_db_connection()
    reqs = conn.execute('SELECT * FROM join_requests WHERE room_id = ?', (room_id,)).fetchall()
    conn.close()
    return [dict(r) for r in reqs]

def get_request_by_sid(room_id, sid):
    conn = get_db_connection()
    req = conn.execute('SELECT * FROM join_requests WHERE room_id = ? AND sid = ?', (room_id, sid)).fetchone()
    conn.close()
    return dict(req) if req else None

def approve_user(room_id, user_id, user_name):
    conn = get_db_connection()
    # Add to permissions
    conn.execute('INSERT OR REPLACE INTO room_permissions (room_id, user_id, user_name, is_approved) VALUES (?, ?, ?, 1)',
                 (room_id, user_id, user_name))
    # Remove from requests
    conn.execute('DELETE FROM join_requests WHERE room_id = ? AND user_id = ?', (room_id, user_id))
    conn.commit()
    conn.close()

def deny_user(room_id, user_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM join_requests WHERE room_id = ? AND user_id = ?', (room_id, user_id))
    conn.commit()
    conn.close()

def get_approved_users(room_id):
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM room_permissions WHERE room_id = ? AND is_approved = 1', (room_id,)).fetchall()
    conn.close()
    return [dict(u) for u in users]
