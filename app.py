# Monkey patch for eventlet
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import db

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Database
db.init_db()

# Store users in each room: {room_id: set(session_ids)}
# This tracks ACTIVE connections, which is transient.
room_users = {}

# Store viewer information: {room_id: {session_id: {'name': '...', 'userId': '...'}}}
# This maps active SIDs to user info.
room_viewer_info = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/room/<room_id>')
def room(room_id):
    return render_template('room.html', room_id=room_id)

@socketio.on('join')
def on_join(data):
    room_id = data['room']
    user_name = data.get('name', 'Anonymous')
    user_id = data.get('userId')
    
    # Get room from DB
    room_data = db.get_room(room_id)
    
    # Check if room exists but is empty (in memory) AND not in DB? 
    # Actually, if it's not in DB, it doesn't exist.
    # If it's in DB but no active users, it's fine, users can rejoin.
    # The original logic was: "Check if room exists but is empty (was closed)"
    # With DB, if it exists in DB, it's open. If not, it's closed.
    
    # New room – first user becomes host
    if not room_data:
        # Create room in DB
        if db.create_room(room_id, user_id, request.sid, user_name):
            join_room(room_id)
            
            if room_id not in room_users:
                room_users[room_id] = set()
            room_users[room_id].add(request.sid)
            
            # Store viewer info for host too
            if room_id not in room_viewer_info:
                room_viewer_info[room_id] = {}
            room_viewer_info[room_id][request.sid] = {'name': user_name, 'userId': user_id}
            
            print(f"Room {room_id} created by {request.sid} ({user_name}, ID: {user_id})")
            
            emit('host_status', {'isHost': True}, to=request.sid)
            emit('viewer_count', {'count': 0}, room=room_id)
        else:
            emit('error', {'message': 'Failed to create room.'})
        return
    
    # Existing room – determine role
    is_host = (room_data['host_id'] == user_id)
    
    if is_host:
        # Update host SID in DB
        db.update_room_host_sid(room_id, request.sid)
            
        # Host rejoining
        join_room(room_id)
        if room_id not in room_users:
            room_users[room_id] = set()
        room_users[room_id].add(request.sid)
        
        # Update viewer info
        if room_id not in room_viewer_info:
            room_viewer_info[room_id] = {}
        room_viewer_info[room_id][request.sid] = {'name': user_name, 'userId': user_id}
        
        emit('host_status', {'isHost': True}, to=request.sid)
        
        # Send current state
        current_state = {
            'videoId': room_data['video_id'],
            'isPlaying': bool(room_data['is_playing']),
            'time': room_data['current_time']
        }
        if current_state['videoId']:
            emit('current_state', current_state, to=request.sid)
            
        # Send pending requests to host
        pending = db.get_pending_requests(room_id)
        for req in pending:
            # We need to send the SID that is currently connected? 
            # Wait, if the user disconnected, the SID in DB is old.
            # But if they are waiting, they are connected.
            # We should check if the SID in pending request is still in room_users?
            # Actually, if they are pending, they might not be in room_users yet?
            # In original logic, they are NOT in room_users until approved.
            # So we just send the request.
            emit('join_request', {'sid': req['sid'], 'name': req['user_name']}, to=request.sid)
            
        total = len(room_users[room_id])
        emit('viewer_count', {'count': total - 1}, room=room_id)
        print(f"Host {request.sid} rejoined room: {room_id}")
        
    elif db.is_user_approved(room_id, user_id):
        # Approved viewer rejoining
        join_room(room_id)
        if room_id not in room_users:
            room_users[room_id] = set()
        room_users[room_id].add(request.sid)
        
        # Store viewer info
        if room_id not in room_viewer_info:
            room_viewer_info[room_id] = {}
        room_viewer_info[room_id][request.sid] = {'name': user_name, 'userId': user_id}
            
        emit('host_status', {'isHost': False}, to=request.sid)
        
        current_state = {
            'videoId': room_data['video_id'],
            'isPlaying': bool(room_data['is_playing']),
            'time': room_data['current_time']
        }
        if current_state['videoId']:
            emit('current_state', current_state, to=request.sid)
            
        total = len(room_users[room_id])
        emit('viewer_count', {'count': total - 1}, room=room_id)
        print(f"Approved viewer {request.sid} ({user_name}) rejoined room: {room_id}")
        
    else:
        # New viewer – send join request to host
        # Add to DB
        db.add_join_request(room_id, user_id, user_name, request.sid)
        
        # Notify host
        # Need to get current host SID from DB
        # But wait, DB might have old SID if host disconnected.
        # But if host is connected, they should be in room_users?
        # Actually, we can just emit to the room? No, join_request is private to host.
        # We can try sending to the host_sid from DB.
        host_sid = room_data['host_sid']
        if host_sid:
            emit('join_request', {'sid': request.sid, 'name': user_name}, to=host_sid)
            
        emit('waiting_approval', {'message': 'Waiting for host approval...'}, to=request.sid)
        print(f"Join request from {user_name} ({request.sid}) for room {room_id}")

@socketio.on('sync_action')
def on_sync_action(data):
    room_id = data['room']
    action = data['action']
    time_val = data['time']
    
    print(f"Sync action in {room_id}: {action} at {time_val}")
    
    # Update DB
    db.update_room_state(room_id, is_playing=(action == 'play'), current_time=time_val)
    
    emit('sync_action', data, room=room_id, include_self=False)

@socketio.on('change_video')
def on_change_video(data):
    room_id = data['room']
    videoId = data['videoId']
    
    room_data = db.get_room(room_id)
    if not room_data:
        emit('error', {'message': 'Room does not exist'}, to=request.sid)
        return
    
    # Only allow host to change video
    # Check against DB host_id or check if current SID matches host_sid
    if room_data['host_sid'] != request.sid:
        emit('error', {'message': 'Only the host can change the video'}, to=request.sid)
        print(f"Non-host {request.sid} attempted to change video in {room_id}")
        return
    
    print(f"Video changed in {room_id}: {videoId}")
    
    # Update DB
    db.update_room_state(room_id, video_id=videoId, is_playing=False, current_time=0)
    
    emit('change_video', data, room=room_id)

@socketio.on('approve_join')
def on_approve_join(data):
    room_id = data['room']
    viewer_sid = data['viewer_sid']
    
    room_data = db.get_room(room_id)
    if not room_data or room_data['host_sid'] != request.sid:
        return
    
    # Get request details from DB
    req = db.get_request_by_sid(room_id, viewer_sid)
    if not req:
        return
        
    user_id = req['user_id']
    user_name = req['user_name']
    
    # Approve in DB
    db.approve_user(room_id, user_id, user_name)
    
    # Add viewer to room and room_users
    try:
        join_room(room_id, sid=viewer_sid)
    except Exception as e:
        print(f"Error joining room: {e}")
        
    if room_id not in room_users:
        room_users[room_id] = set()
    room_users[room_id].add(viewer_sid)
    
    # Store viewer info
    if room_id not in room_viewer_info:
        room_viewer_info[room_id] = {}
    room_viewer_info[room_id][viewer_sid] = {'name': user_name, 'userId': user_id}
    
    # Notify viewer they were approved
    emit('join_approved', {'room': room_id}, to=viewer_sid)
    
    # Send viewer their status and current video state
    emit('host_status', {'isHost': False}, to=viewer_sid)
    
    current_state = {
        'videoId': room_data['video_id'],
        'isPlaying': bool(room_data['is_playing']),
        'time': room_data['current_time']
    }
    if current_state['videoId']:
        emit('current_state', current_state, to=viewer_sid)
    
    # Update viewer count for everyone in the room
    total_users = len(room_users[room_id])
    viewer_count = total_users - 1
    emit('viewer_count', {'count': viewer_count}, room=room_id)
    
    print(f"Viewer {viewer_sid} (ID: {user_id}) approved to join room {room_id}")

@socketio.on('deny_join')
def on_deny_join(data):
    room_id = data['room']
    viewer_sid = data['viewer_sid']
    
    room_data = db.get_room(room_id)
    if not room_data or room_data['host_sid'] != request.sid:
        return
    
    # Get request details to get name
    req = db.get_request_by_sid(room_id, viewer_sid)
    viewer_name = req['user_name'] if req else "User"
    
    # Deny in DB (remove request)
    if req:
        db.deny_user(room_id, req['user_id'])
    
    # Notify viewer they were denied with their name
    emit('join_denied', {
        'message': f'Sorry {viewer_name}, the host denied your request to join this room.'
    }, to=viewer_sid)
    
    print(f"Viewer {viewer_sid} denied from room {room_id}")

@socketio.on('request_sync')
def on_request_sync(data):
    room_id = data['room']
    room_data = db.get_room(room_id)
    if room_data:
        current_state = {
            'videoId': room_data['video_id'],
            'isPlaying': bool(room_data['is_playing']),
            'time': room_data['current_time']
        }
        emit('current_state', current_state, to=request.sid)

@socketio.on('get_viewers')
def on_get_viewers(data):
    room_id = data['room']
    
    room_data = db.get_room(room_id)
    if not room_data or room_data['host_sid'] != request.sid:
        return
    
    # Get list of viewers (excluding host)
    # We use the in-memory room_users to know who is ONLINE
    # And room_viewer_info to get their names
    viewers = []
    if room_id in room_viewer_info:
        for sid, info in room_viewer_info[room_id].items():
            if sid in room_users.get(room_id, set()) and sid != room_data['host_sid']:
                viewers.append({
                    'name': info.get('name', 'Anonymous'),
                    'userId': info.get('userId', '')
                })
    
    emit('viewers_list', {'viewers': viewers}, to=request.sid)
    print(f"Host {request.sid} requested viewer list for room {room_id}: {len(viewers)} viewers")

@socketio.on('disconnect')
def on_disconnect():
    print(f"User {request.sid} disconnected")
    
    # Find which room the user was in
    for room_id in list(room_users.keys()):
        if request.sid in room_users[room_id]:
            # Check if this user was the host
            room_data = db.get_room(room_id)
            was_host = room_data and room_data['host_sid'] == request.sid
            
            # Remove user from room_users (memory)
            room_users[room_id].discard(request.sid)
            leave_room(room_id)
            
            # Remove from room_viewer_info
            if room_id in room_viewer_info and request.sid in room_viewer_info[room_id]:
                del room_viewer_info[room_id][request.sid]
            
            if was_host:
                # Host left - close the room completely
                print(f"Host left room {room_id}, closing room")
                
                # Notify all remaining users that the room is closing
                emit('error', {'message': 'The host has left. This room is now closed.'}, room=room_id)
                
                # Clean up the room completely from DB
                db.delete_room(room_id)
                
                # Clean up memory
                if room_id in room_users:
                    del room_users[room_id]
                if room_id in room_viewer_info:
                    del room_viewer_info[room_id]
            else:
                # Regular user left - update viewer count
                if len(room_users[room_id]) > 0:
                    total_users = len(room_users[room_id])
                    viewer_count = total_users - 1  # Exclude the host
                    emit('viewer_count', {'count': viewer_count}, room=room_id)
                else:
                    # No users left, clean up the room
                    db.delete_room(room_id)
                    if room_id in room_users:
                        del room_users[room_id]
                    if room_id in room_viewer_info:
                        del room_viewer_info[room_id]

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
