# Monkey patch for eventlet
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store room state: {room_id: {'videoId': '...', 'isPlaying': False, 'time': 0, 'host': 'sid', 'hostId': 'uid'}}
rooms = {}

# Store users in each room: {room_id: set(session_ids)}
room_users = {}

# Store approved user IDs for each room: {room_id: set(user_ids)}
room_approved_users = {}

# Store pending join requests: {room_id: {session_id: {'name': '...', 'userId': '...'}}}
pending_requests = {}

# Store viewer information: {room_id: {session_id: {'name': '...', 'userId': '...'}}}
room_viewer_info = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/room/<room_id>')
def room(room_id):
    return render_template('room.html', room_id=room_id)

@socketio.on('join')
def on_join(data):
    room = data['room']
    user_name = data.get('name', 'Anonymous')
    user_id = data.get('userId')
    
    # Check if room exists but is empty (was closed)
    if room in rooms and (room not in room_users or len(room_users[room]) == 0):
        emit('error', {'message': 'This room has been closed. Please create a new room.'})
        return
    
    # New room – first user becomes host
    if room not in rooms:
        join_room(room)
        rooms[room] = {
            'videoId': None,
            'isPlaying': False,
            'time': 0,
            'host': request.sid,
            'hostId': user_id
        }
        room_users[room] = set()
        room_users[room].add(request.sid)
        room_approved_users[room] = set()
        pending_requests[room] = {}
        
        print(f"Room {room} created by {request.sid} ({user_name}, ID: {user_id})")
        
        emit('host_status', {'isHost': True}, to=request.sid)
        emit('viewer_count', {'count': 0}, room=room)
        return
    
    # Existing room – determine role
    # Check if host rejoining (by ID or SID)
    is_host = (rooms[room].get('hostId') == user_id) or (rooms[room]['host'] == request.sid)
    
    if is_host:
        # Update host SID if changed
        if rooms[room]['host'] != request.sid:
            rooms[room]['host'] = request.sid
            
        # Host rejoining
        join_room(room)
        if request.sid not in room_users[room]:
            room_users[room].add(request.sid)
        emit('host_status', {'isHost': True}, to=request.sid)
        if rooms[room].get('videoId'):
            emit('current_state', rooms[room], to=request.sid)
        total = len(room_users[room])
        emit('viewer_count', {'count': total - 1}, room=room)
        print(f"Host {request.sid} rejoined room: {room}")
        
    elif (room in room_approved_users and user_id in room_approved_users[room]) or (request.sid in room_users[room]):
        # Approved viewer rejoining
        join_room(room)
        if request.sid not in room_users[room]:
            room_users[room].add(request.sid)
        
        # Store viewer info
        if room not in room_viewer_info:
            room_viewer_info[room] = {}
        room_viewer_info[room][request.sid] = {'name': user_name, 'userId': user_id}
            
        emit('host_status', {'isHost': False}, to=request.sid)
        if rooms[room].get('videoId'):
            emit('current_state', rooms[room], to=request.sid)
        total = len(room_users[room])
        emit('viewer_count', {'count': total - 1}, room=room)
        print(f"Approved viewer {request.sid} ({user_name}) rejoined room: {room}")
        
    else:
        # New viewer – send join request to host
        if room not in pending_requests:
            pending_requests[room] = {}
            
        # Check if this user already has a pending request
        existing_request = False
        # We need to use list() to avoid runtime error if dict changes during iteration
        for sid in list(pending_requests[room].keys()):
            req = pending_requests[room][sid]
            if req.get('userId') == user_id:
                # Update SID for existing request
                del pending_requests[room][sid]
                pending_requests[room][request.sid] = {'name': user_name, 'userId': user_id}
                existing_request = True
                break
        
        if not existing_request:
            pending_requests[room][request.sid] = {'name': user_name, 'userId': user_id}
            
        emit('join_request', {'sid': request.sid, 'name': user_name}, to=rooms[room]['host'])
        emit('waiting_approval', {'message': 'Waiting for host approval...'}, to=request.sid)
        print(f"Join request from {user_name} ({request.sid}) for room {room}")

@socketio.on('sync_action')
def on_sync_action(data):
    room = data['room']
    action = data['action']
    time = data['time']
    
    print(f"Sync action in {room}: {action} at {time}")
    
    if room not in rooms:
        rooms[room] = {}
    
    rooms[room]['isPlaying'] = (action == 'play')
    rooms[room]['time'] = time
    
    emit('sync_action', data, room=room, include_self=False)

@socketio.on('change_video')
def on_change_video(data):
    room = data['room']
    videoId = data['videoId']
    
    # Only allow host to change video
    if room not in rooms:
        emit('error', {'message': 'Room does not exist'}, to=request.sid)
        return
    
    if rooms[room]['host'] != request.sid:
        emit('error', {'message': 'Only the host can change the video'}, to=request.sid)
        print(f"Non-host {request.sid} attempted to change video in {room}")
        return
    
    print(f"Video changed in {room}: {videoId}")
    
    rooms[room]['videoId'] = videoId
    rooms[room]['isPlaying'] = False
    rooms[room]['time'] = 0
    
    emit('change_video', data, room=room)

@socketio.on('approve_join')
def on_approve_join(data):
    room = data['room']
    viewer_sid = data['viewer_sid']
    
    # Verify requester is the host
    if room not in rooms or rooms[room]['host'] != request.sid:
        return
    
    # Get userId and name from pending request
    user_id = None
    user_name = 'Anonymous'
    if room in pending_requests and viewer_sid in pending_requests[room]:
        user_id = pending_requests[room][viewer_sid].get('userId')
        user_name = pending_requests[room][viewer_sid].get('name', 'Anonymous')
        del pending_requests[room][viewer_sid]
    
    # Add viewer to room and room_users
    try:
        join_room(room, sid=viewer_sid)
    except Exception as e:
        print(f"Error joining room: {e}")
        
    if room not in room_users:
        room_users[room] = set()
    room_users[room].add(viewer_sid)
    
    # Store viewer info
    if room not in room_viewer_info:
        room_viewer_info[room] = {}
    room_viewer_info[room][viewer_sid] = {'name': user_name, 'userId': user_id}
    
    # Add to approved users list
    if user_id:
        if room not in room_approved_users:
            room_approved_users[room] = set()
        room_approved_users[room].add(user_id)
    
    # Notify viewer they were approved
    emit('join_approved', {'room': room}, to=viewer_sid)
    
    # Send viewer their status and current video state
    emit('host_status', {'isHost': False}, to=viewer_sid)
    if rooms[room].get('videoId'):
        emit('current_state', rooms[room], to=viewer_sid)
    
    # Update viewer count for everyone in the room
    total_users = len(room_users[room])
    viewer_count = total_users - 1
    emit('viewer_count', {'count': viewer_count}, room=room)
    
    print(f"Viewer {viewer_sid} (ID: {user_id}) approved to join room {room}")

@socketio.on('deny_join')
def on_deny_join(data):
    room = data['room']
    viewer_sid = data['viewer_sid']
    
    # Verify requester is the host
    if room not in rooms or rooms[room]['host'] != request.sid:
        return
    
    # Remove from pending requests
    if room in pending_requests and viewer_sid in pending_requests[room]:
        viewer_name = pending_requests[room][viewer_sid]['name']
        del pending_requests[room][viewer_sid]
    else:
        viewer_name = "User"
    
    # Notify viewer they were denied with their name
    emit('join_denied', {
        'message': f'Sorry {viewer_name}, the host denied your request to join this room.'
    }, to=viewer_sid)
    
    print(f"Viewer {viewer_sid} denied from room {room}")

@socketio.on('request_sync')
def on_request_sync(data):
    room = data['room']
    if room in rooms:
        emit('current_state', rooms[room], to=request.sid)

@socketio.on('get_viewers')
def on_get_viewers(data):
    room = data['room']
    
    # Verify requester is the host
    if room not in rooms or rooms[room]['host'] != request.sid:
        return
    
    # Get list of viewers (excluding host)
    viewers = []
    if room in room_viewer_info:
        for sid, info in room_viewer_info[room].items():
            if sid in room_users.get(room, set()) and sid != rooms[room]['host']:
                viewers.append({
                    'name': info.get('name', 'Anonymous'),
                    'userId': info.get('userId', '')
                })
    
    emit('viewers_list', {'viewers': viewers}, to=request.sid)
    print(f"Host {request.sid} requested viewer list for room {room}: {len(viewers)} viewers")

@socketio.on('disconnect')
def on_disconnect():
    print(f"User {request.sid} disconnected")
    
    # Find which room the user was in
    for room in list(room_users.keys()):
        if request.sid in room_users[room]:
            # Check if this user was the host
            was_host = room in rooms and rooms[room]['host'] == request.sid
            
            # Remove user from room
            room_users[room].discard(request.sid)
            leave_room(room)
            
            if was_host:
                # Host left - close the room completely
                print(f"Host left room {room}, closing room")
                
                # Notify all remaining users that the room is closing
                emit('error', {'message': 'The host has left. This room is now closed.'}, room=room)
                
                # Clean up the room completely
                if room in rooms:
                    del rooms[room]
                if room in room_users:
                    del room_users[room]
            else:
                # Regular user left - update viewer count
                if len(room_users[room]) > 0:
                    total_users = len(room_users[room])
                    viewer_count = total_users - 1  # Exclude the host
                    emit('viewer_count', {'count': viewer_count}, room=room)
                else:
                    # No users left, clean up the room
                    if room in rooms:
                        del rooms[room]
                    if room in room_users:
                        del room_users[room]

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
