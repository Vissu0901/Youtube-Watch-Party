# Database Integration for Youtube-Watch Sync

This project now uses SQLite3 to manage room state, user permissions, and join requests. This ensures that the approval process is robust and state is maintained even if the application process restarts (provided the database file is preserved).

## Database Schema

The database `youtube_watch.db` is automatically created on startup. It contains the following tables:

### 1. `rooms`
Stores the current state of each active room.
- `room_id` (TEXT, PK): Unique identifier for the room.
- `host_id` (TEXT): User ID of the host.
- `host_sid` (TEXT): Current Socket ID of the host (transient).
- `video_id` (TEXT): ID of the YouTube video currently loaded.
- `is_playing` (INTEGER): 1 if playing, 0 if paused.
- `current_time` (REAL): Current timestamp of the video.
- `created_at` (REAL): Timestamp when the room was created.

### 2. `room_permissions`
Stores the list of users who have been approved to join a room.
- `room_id` (TEXT, FK): Reference to the room.
- `user_id` (TEXT): User ID of the approved viewer.
- `user_name` (TEXT): Display name of the viewer.
- `is_approved` (INTEGER): 1 if approved.

### 3. `join_requests`
Stores pending requests from users wanting to join a room.
- `room_id` (TEXT, FK): Reference to the room.
- `user_id` (TEXT): User ID of the requester.
- `user_name` (TEXT): Display name of the requester.
- `sid` (TEXT): Socket ID of the requester.
- `created_at` (REAL): Timestamp of the request.

## Production Deployment Notes

### SQLite Persistence
Since SQLite uses a local file (`youtube_watch.db`), this file **must be persisted**.

-   **VPS / Dedicated Server**: No special action needed. The file will persist on the disk.
-   **Docker**: Mount a volume to persist the database file.
    ```bash
    docker run -v $(pwd)/data:/app/data ...
    ```
    (You may need to adjust the DB path in `db.py` to point to the mounted volume).
-   **Heroku**: SQLite is **not supported** for persistence on Heroku (ephemeral filesystem). You will lose data on restart.
-   **Vercel / Serverless**: SQLite is **not supported** for persistence. You will lose data on every deployment and potentially on every request/cold start.

**Recommendation for Vercel/Heroku**:
If you plan to deploy to a platform with an ephemeral filesystem, you should modify `db.py` to use a hosted database service like **PostgreSQL** (e.g., Vercel Postgres, Supabase, Neon) or **Redis**.
