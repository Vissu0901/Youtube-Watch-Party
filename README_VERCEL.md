# Vercel Deployment Guide

This application uses Flask-SocketIO, which has specific requirements when deployed to serverless platforms like Vercel.

## Configuration Changes
We have switched the async mode to `threading` to improve compatibility with Vercel's serverless environment.

## Limitations on Vercel
Vercel Serverless Functions have a maximum execution time (usually 10-60 seconds) and do not support persistent WebSocket connections.

1.  **Connection Issues**: You may experience frequent disconnects or "Disconnected" status because the serverless function shuts down.
2.  **Polling**: The client will likely fall back to HTTP long-polling.
3.  **Persistence**: The SQLite database (`youtube_watch.db`) is **ephemeral** on Vercel. Data (rooms, permissions) will be lost on every deployment and potentially on every cold start.

## Recommended Hosting
For a production-grade experience with WebSockets and persistent data, we strongly recommend deploying to a VPS or a platform that supports persistent applications:
-   **Render** (Has a free tier for Web Services)
-   **Railway**
-   **DigitalOcean App Platform**
-   **Heroku**
-   **Fly.io**

If you must use Vercel, consider using an external database (like Vercel Postgres) and an external WebSocket service (like Pusher) instead of Flask-SocketIO.
