## 📋 Phase 1: The Core Backend (Vanilla PHP)
Build the foundation first so all other components have something to talk to.

   1. Set Up HTTPS Hosting: PWA Service Workers and Web Push require HTTPS. Set up your web hosting environment early (even a free tier host or local tunnel tool like Ngrok/Cloudflare Tunnels works for development, as long as it provides an https:// URL).
   2. Database Setup: Create a simple database with two tables:
      * `subscriptions`: To store user PWA push tokens (`endpoint`, `p256dh` key, `auth` key).
      * `fire_history`: To log when a fire was detected (`id`, `timestamp`, `confidence_score`, etc.).
   3. Build the API Endpoints: Write two simple endpoints:
      * Receives JSON from your PWA and saves it to the database.
      * Receives a POST request from your Python script, inserts the log into fire_history, and eventually triggers the push logic.
   
## 📱 Phase 2: The PWA Frontend (HTML/JS)
Build the receiver next. By doing this second, you can generate the push subscription and test your PHP server's ability to send notifications.

   1. Manifest & Basic UI: Create a basic `index.html` (to display the fire report history from `fire_history`) and a `manifest.json` file so the phone recognizes it as an installable app.
   2. Service Worker Registration: Write a basic `sw.js` file that handles the background `push` event and calls `self.registration.showNotification()`.
   3. Request Permission & Subscribe: Add JavaScript to your UI to request notification permissions, use your VAPID public key to get a browser endpoint token, and `fetch()` POST it to your PHP save subscription endpoint.
   4. The "Hardcoded" Test: Manually trigger a test notification from your PHP server to your phone to ensure the keys, database storage, and Service Worker are perfectly synced.

## 🐍 Phase 3: The Python Detection Loop (YOLOv8)

Wire the currently existing fire detection script into the backend