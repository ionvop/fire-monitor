const functions = require('firebase-functions');
const admin = require('firebase-admin');
admin.initializeApp();

// Sends a push notification whenever a NEW fire alert document is created.
// Only "detected" alerts trigger a notification (a "retracted" event is a
// resolution, not a fresh fire).
//
// The controller writes a document to the `alerts` collection on every fire
// detection/retraction, so this function covers push delivery without any
// controller changes.
exports.sendFireAlertPush = functions.firestore
  .document('alerts/{alertId}')
  .onCreate((snap, context) => {
    const alert = snap.data();

    // Only notify on brand-new detections, not retractions.
    if (alert.status !== 'detected') {
      console.log(`Skipping push for status=${alert.status}`);
      return null;
    }

    const confidence = alert.confidence
      ? `Confidence ${Math.round(alert.confidence * 100)}%`
      : 'Fire detected';
    const title = '🔥 Fire detected!';

    const payload = {
      notification: {
        title,
        body: confidence,
      },
      android: {
        notification: {
          channelId: 'fire_alerts',
        },
      },
      data: {
        alertId: snap.id,
        status: alert.status,
        // Convert Firestore Timestamp to millis for easy parsing in the app.
        timestamp: String(
          alert.timestamp ? alert.timestamp.toMillis() : Date.now()
        ),
      },
      topic: 'alerts',
    };

    console.log(`Sending push for alert ${snap.id}`);
    return admin.messaging().send(payload);
  });