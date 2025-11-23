# 🎥 Youtube-Watch Party

A real-time synchronized YouTube watch party application built with Flask and Socket.IO. Watch YouTube videos together with friends in perfect sync!

## ✨ Features

- **Real-time Synchronization**: Watch videos in perfect sync with all participants
- **Host Controls**: Host can load videos and control playback
- **Join Request System**: Viewers must be approved by the host before joining
- **Viewer Management**: Host can see all connected viewers
- **Dynamic Layout**: UI adapts based on notifications and user role
- **Modern UI/UX**: Beautiful gradient design with smooth animations
- **Responsive Design**: Works seamlessly on desktop and mobile devices

## 🚀 Getting Started

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Vissu0901/Youtube-Watch-Party.git
cd Youtube-Watch-Party
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and navigate to:
```
http://localhost:5000
```

## 📖 How to Use

### As a Host:
1. Click "Create Room" on the home page
2. Enter your name
3. Share the Room ID with your friends
4. Approve join requests from viewers
5. Load YouTube videos using the URL input
6. Control playback - all viewers will be synchronized

### As a Viewer:
1. Click "Join Room" on the home page
2. Enter your name and the Room ID
3. Wait for host approval
4. Enjoy synchronized video playback!

## 🛠️ Technologies Used

- **Backend**: Flask, Flask-SocketIO
- **Frontend**: HTML5, CSS3, JavaScript
- **Real-time Communication**: Socket.IO
- **Video Player**: YouTube IFrame API

## 📁 Project Structure

```
Youtube-Watch/
├── app.py                 # Main Flask application
├── templates/
│   ├── base.html         # Base template
│   ├── index.html        # Home page
│   └── room.html         # Watch party room
├── static/
│   ├── css/
│   │   └── style.css     # Styles
│   ├── js/
│   │   └── room.js       # Room functionality
│   └── favicon.png       # App icon
└── requirements.txt      # Python dependencies
```

## 🎨 Features in Detail

### Synchronization
- Play/Pause actions are synchronized across all viewers
- Seek operations maintain perfect sync
- Automatic state recovery for reconnecting users

### Security
- Join request approval system
- Host-only controls
- Session-based user identification

### UI/UX
- Gradient design with red-to-blue theme
- Animated status indicators
- Smooth transitions and hover effects
- Responsive layout that adapts to content

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is open source and available under the MIT License.

## 👤 Author

**Vissu0901**
- GitHub: [@Vissu0901](https://github.com/Vissu0901)

## 🙏 Acknowledgments

- YouTube IFrame API for video playback
- Socket.IO for real-time communication
- Flask framework for the backend

---

Made with ❤️ for watching videos together
