// Socket.io client for YouTube Watch Party
var socket = io();
var player;
var isHost = false;
var ignoreNextEvent = false;

// Connection status UI
socket.on('connect', function () {
    const status = document.getElementById('connectionStatus');
    status.innerHTML = '<span class="status-dot"></span>Connected';


    const userName = sessionStorage.getItem('userName') || 'Anonymous';
    let userId = sessionStorage.getItem('userId');
    if (!userId) {
        userId = 'user_' + Math.random().toString(36).substr(2, 9);
        sessionStorage.setItem('userId', userId);
    }

    socket.emit('join', { room: ROOM_ID, name: userName, userId: userId });
});

socket.on('disconnect', function (reason) {
    const status = document.getElementById('connectionStatus');
    status.innerText = 'Disconnected';
    status.style.color = '#ff4b4b';
    status.style.borderColor = 'rgba(255, 75, 75, 0.3)';
    status.style.background = 'rgba(255, 75, 75, 0.2)';
    console.log('Socket disconnected:', reason);
});

socket.on('connect_error', function (error) {
    const status = document.getElementById('connectionStatus');
    status.innerText = 'Conn Error';
    status.title = error;
    status.style.color = '#ff4b4b';
    console.log('Connection error:', error);
});

// YouTube Iframe API
function onYouTubeIframeAPIReady() {
    player = new YT.Player('player', {
        height: '100%',
        width: '100%',
        videoId: '',
        playerVars: { playsinline: 1, controls: 1, rel: 0 },
        events: { onReady: onPlayerReady, onStateChange: onPlayerStateChange }
    });
}

function onPlayerReady(event) {
    socket.emit('request_sync', { room: ROOM_ID });
}

function onPlayerStateChange(event) {
    if (ignoreNextEvent) {
        ignoreNextEvent = false;
        return;
    }
    const state = event.data;
    const time = player.getCurrentTime();
    if (state === YT.PlayerState.PLAYING) {
        socket.emit('sync_action', { room: ROOM_ID, action: 'play', time: time });
    } else if (state === YT.PlayerState.PAUSED) {
        socket.emit('sync_action', { room: ROOM_ID, action: 'pause', time: time });
    }
}

function loadVideo() {
    if (!isHost) {
        alert('Only the host can load videos');
        return;
    }
    const url = document.getElementById('videoUrlInput').value;
    const videoId = extractVideoID(url);
    if (videoId) {
        socket.emit('change_video', { room: ROOM_ID, videoId: videoId });
    } else {
        alert('Invalid YouTube URL');
    }
}

function copyRoomId() {
    const roomId = document.getElementById('currentRoomId').innerText;
    navigator.clipboard.writeText(roomId).then(() => {
        const btn = document.querySelector('.copy-btn');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.innerHTML = originalHTML;
            btn.classList.remove('copied');
        }, 2000);
    });
}

function extractVideoID(url) {
    const regExp = /^.*((youtu.be\/)|(v\/)|(\/u\/\w\/)|(embed\/)|(watch\?))\??v?=?([^#&?]*).*/;
    const match = url.match(regExp);
    return (match && match[7] && match[7].length === 11) ? match[7] : false;
}


function leaveRoom() {
    window.location.href = '/';
}

function approveJoin(viewerSid) {
    socket.emit('approve_join', { room: ROOM_ID, viewer_sid: viewerSid });
    const requestDiv = document.getElementById('request-' + viewerSid);
    if (requestDiv) requestDiv.remove();
    updateLeftColumnVisibility();
}

function denyJoin(viewerSid) {
    socket.emit('deny_join', { room: ROOM_ID, viewer_sid: viewerSid });
    const requestDiv = document.getElementById('request-' + viewerSid);
    if (requestDiv) requestDiv.remove();
    updateLeftColumnVisibility();
}

// Update left column visibility based on join requests
function updateLeftColumnVisibility() {
    if (!isHost) return;

    const leftColumn = document.getElementById('leftColumn');
    const joinRequestList = document.getElementById('joinRequestList');
    const panel = document.getElementById('joinRequestPanel');

    // Check if there are any join requests
    const hasRequests = joinRequestList && joinRequestList.children.length > 0;

    if (leftColumn) {
        leftColumn.style.display = hasRequests ? 'block' : 'none';
    }

    if (panel) {
        panel.style.display = hasRequests ? 'block' : 'none';
    }
}

// Socket event handlers
socket.on('sync_action', function (data) {
    if (!player || !player.seekTo) return;
    ignoreNextEvent = true;
    if (data.action === 'play') {
        player.seekTo(data.time);
        player.playVideo();
    } else if (data.action === 'pause') {
        player.seekTo(data.time);
        player.pauseVideo();
    }
});

socket.on('change_video', function (data) {
    if (player && player.loadVideoById) {
        player.loadVideoById(data.videoId);
    }
});

socket.on('current_state', function (data) {
    if (data.videoId && player && player.loadVideoById) {
        ignoreNextEvent = true;
        player.loadVideoById(data.videoId);
        setTimeout(() => {
            if (data.time) player.seekTo(data.time, true);
            if (data.isPlaying) player.playVideo();
            else player.pauseVideo();
        }, 500);
    }
});

socket.on('host_status', function (data) {
    isHost = data.isHost;
    const controls = document.getElementById('hostControls');
    const leftColumn = document.getElementById('leftColumn');

    if (controls) controls.style.display = isHost ? 'flex' : 'none';
    if (leftColumn) leftColumn.style.display = isHost ? 'block' : 'none';
});

socket.on('error', function (data) {
    alert(data.message);
});

socket.on('viewer_count', function (data) {
    const viewerCountElement = document.getElementById('viewerCountNumber');
    viewerCountElement.innerText = data.count === 0 ? 'No' : data.count;
});

socket.on('join_request', function (data) {
    const panel = document.getElementById('joinRequestPanel');
    const list = document.getElementById('joinRequestList');
    const requestDiv = document.createElement('div');
    requestDiv.id = 'request-' + data.sid;
    requestDiv.style.cssText = 'display: flex; flex-direction: column; gap: 0.75rem; padding: 1rem; background: rgba(0,0,0,0.3); border-radius: 8px; margin-bottom: 0.5rem; border: 1px solid rgba(255,255,255,0.1);';
    requestDiv.innerHTML = `
        <div style="display: flex; align-items: baseline; gap: 0.5rem;">
            <span style="font-weight: bold; font-size: 1.1rem;">${data.name}</span>
            <span style="font-size: 0.9rem; opacity: 0.7;">wants to join</span>
        </div>
        <div style="display: flex; gap: 0.5rem; width: 100%;">
            <button onclick="approveJoin('${data.sid}')" class="btn btn-blue" style="flex: 1; padding: 8px; display: flex; justify-content: center; align-items: center; gap: 6px; font-size: 0.9rem;">
                <span>✓</span> Accept
            </button>
            <button onclick="denyJoin('${data.sid}')" class="btn btn-red" style="flex: 1; padding: 8px; display: flex; justify-content: center; align-items: center; gap: 6px; font-size: 0.9rem;">
                <span>✕</span> Deny
            </button>
        </div>
    `;
    list.appendChild(requestDiv);
    updateLeftColumnVisibility();
});

socket.on('waiting_approval', function (data) {
    document.getElementById('waitingScreen').style.display = 'block';
    document.getElementById('videoPlayer').style.display = 'none';
});

socket.on('join_approved', function (data) {
    document.getElementById('waitingScreen').style.display = 'none';
    document.getElementById('videoPlayer').style.display = 'block';
});

socket.on('join_denied', function (data) {
    const waitingScreen = document.getElementById('waitingScreen');
    waitingScreen.innerHTML = `
        <div style="font-size: 3rem; margin-bottom: 1rem;">❌</div>
        <h3 style="color: #ff4b4b;">Request Denied</h3>
        <p style="opacity: 0.8; font-size: 0.9rem;">${data.message}</p>
        <p style="opacity: 0.6; font-size: 0.85rem; margin-top: 1rem;">Redirecting to home page...</p>
    `;
    setTimeout(() => {
        window.location.href = '/';
    }, 3000);
});

// Viewer list functions
function showViewers() {
    if (!isHost) return;
    socket.emit('get_viewers', { room: ROOM_ID });
}

function closeViewersModal() {
    document.getElementById('viewersModal').style.display = 'none';
}

socket.on('viewers_list', function (data) {
    const modal = document.getElementById('viewersModal');
    const list = document.getElementById('viewersList');

    list.innerHTML = '';

    if (data.viewers.length === 0) {
        list.innerHTML = '<p style="opacity: 0.6; text-align: center; padding: 1rem;">No viewers connected</p>';
    } else {
        data.viewers.forEach(viewer => {
            const item = document.createElement('div');
            item.className = 'viewer-item';
            item.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                </svg>
                <span>${viewer.name}</span>
            `;
            list.appendChild(item);
        });
    }

    modal.style.display = 'flex';
});

// Close modal when clicking outside
document.addEventListener('click', function (event) {
    const modal = document.getElementById('viewersModal');
    if (event.target === modal) {
        closeViewersModal();
    }
});
