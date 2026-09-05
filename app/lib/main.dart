import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'firebase_options.dart';

/// The Firestore collection that the controller writes fire-detection alerts
/// to. The app listens to this collection in real time and renders each alert
/// as a card. Because the data lives in Firestore, the app works from any
/// network while the user is away from the controller.
const String kAlertsCollection = 'alerts';

/// The maximum number of alerts to keep in the on-screen list. Newer alerts
/// are shown first.
const int kMaxAlerts = 50;

/// Must match the `android.channelId` used by the Cloud Function so local
/// notifications show on a high-importance channel on Android 8+.
const String kNotificationChannelId = 'fire_alerts';

/// Called when a push notification is received while the app is terminated or
/// in the background. Must be a top-level function (not a closure) so it can
/// run in the background isolate.
@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  final alertId = message.data['alertId'];
  print('Background message handled: alertId=$alertId');
}

/// Local-notifications plugin used to show an in-app banner while the
/// foreground and to register the Android notification channel.
final FlutterLocalNotificationsPlugin _localNotifications =
    FlutterLocalNotificationsPlugin();

Future<void> _initLocalNotifications() async {
  const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
  const initSettings = InitializationSettings(android: androidInit);
  await _localNotifications.initialize(initSettings);

  const androidChannel = AndroidNotificationChannel(
    kNotificationChannelId,
    'Fire Alerts',
    description: 'Notifications when a fire is detected',
    importance: Importance.high,
  );
  await _localNotifications
      .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>()
      ?.createNotificationChannel(androidChannel);
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  final messaging = FirebaseMessaging.instance;

  // Register the background handler before messaging is used.
  FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

  // Request permission (iOS shows a prompt; on Android 13+ this requests
  // POST_NOTIFICATIONS).
  final settings = await messaging.requestPermission();
  print('Notification permission: ${settings.authorizationStatus}');

  // Initialize local notifications for in-app banners while foregrounded.
  await _initLocalNotifications();

  runApp(const FireMonitorApp());
}

class FireMonitorApp extends StatelessWidget {
  const FireMonitorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Fire Monitor',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepOrange),
      ),
      home: const AlertsPage(),
    );
  }
}

/// A single fire-detection alert as written by the controller.
///
/// Field names match the document schema the controller writes to the
/// `alerts` collection. All fields are optional so the app degrades
/// gracefully if the controller writes a partial record.
class FireAlert {
  const FireAlert({
    required this.id,
    required this.timestamp,
    this.confidence,
    this.x,
    this.y,
    this.captureImageUrl,
    this.status,
  });

  /// The Firestore document ID.
  final String id;

  /// When the fire was detected.
  final DateTime timestamp;

  /// Detection confidence (0.0 - 1.0), if reported.
  final double? confidence;

  /// Servo pan angle at detection, if reported.
  final double? x;

  /// Servo tilt angle at detection, if reported.
  final double? y;

  /// URL of the annotated capture image, if one was saved.
  final String? captureImageUrl;

  /// Lifecycle status: 'detected' while firing, 'retracted' after.
  final String? status;

  bool get isActive => status == 'detected';

  factory FireAlert.fromSnapshot(QueryDocumentSnapshot<Map<String, dynamic>> doc) {
    final data = doc.data();
    final ts = data['timestamp'];
    return FireAlert(
      id: doc.id,
      timestamp: ts is Timestamp ? ts.toDate() : DateTime.now(),
      confidence: (data['confidence'] as num?)?.toDouble(),
      x: (data['x'] as num?)?.toDouble(),
      y: (data['y'] as num?)?.toDouble(),
      captureImageUrl: data['captureImageUrl'] as String?,
      status: data['status'] as String?,
    );
  }
}

class AlertsPage extends StatelessWidget {
  const AlertsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Fire Monitor'),
        actions: const [
          Padding(
            padding: EdgeInsets.only(right: 16),
            child: Center(child: _ConnectionStatus()),
          ),
        ],
      ),
      body: StreamBuilder<QuerySnapshot<Map<String, dynamic>>>(
        stream: FirebaseFirestore.instance
            .collection(kAlertsCollection)
            .orderBy('timestamp', descending: true)
            .limit(kMaxAlerts)
            .snapshots(),
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return _ErrorView(error: snapshot.error);
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final alerts = snapshot.requireData.docs
              .map(FireAlert.fromSnapshot)
              .toList();
          if (alerts.isEmpty) {
            return const _EmptyView();
          }
          return ListView.builder(
            padding: const EdgeInsets.all(8),
            itemCount: alerts.length,
            itemBuilder: (context, index) => _AlertCard(alert: alerts[index]),
          );
        },
      ),
    );
  }
}

/// A small indicator showing whether the app is currently receiving live
/// updates from Firestore. It reflects the snapshot's metadata: when the data
/// comes from the local cache (e.g. offline), it shows "offline".
class _ConnectionStatus extends StatelessWidget {
  const _ConnectionStatus();

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<QuerySnapshot<Map<String, dynamic>>>(
      stream: FirebaseFirestore.instance
          .collection(kAlertsCollection)
          .limit(1)
          .snapshots(includeMetadataChanges: true),
      builder: (context, snapshot) {
        final fromCache = snapshot.data?.metadata.isFromCache ?? false;
        final color = fromCache ? Colors.orange : Colors.green;
        final label = fromCache ? 'offline' : 'live';
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.circle, size: 10, color: color),
            const SizedBox(width: 6),
            Text(label, style: Theme.of(context).textTheme.bodySmall),
          ],
        );
      },
    );
  }
}

class _AlertCard extends StatelessWidget {
  const _AlertCard({required this.alert});

  final FireAlert alert;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final accent = alert.isActive ? scheme.error : scheme.primary;

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: accent.withValues(alpha: 0.15),
          child: Icon(
            alert.isActive ? Icons.local_fire_department : Icons.check,
            color: accent,
          ),
        ),
        title: Text(
          alert.isActive ? 'Fire detected' : 'Fire resolved',
          style: TextStyle(color: accent, fontWeight: FontWeight.bold),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text(_formatTimestamp(alert.timestamp)),
            if (alert.confidence != null)
              Text('Confidence: ${(alert.confidence! * 100).toStringAsFixed(0)}%'),
            if (alert.x != null || alert.y != null)
              Text('Position: X ${alert.x?.toStringAsFixed(0) ?? '?'}° · '
                  'Y ${alert.y?.toStringAsFixed(0) ?? '?'}°'),
          ],
        ),
        isThreeLine: true,
      ),
    );
  }

  String _formatTimestamp(DateTime ts) {
    final local = ts.toLocal();
    final hh = local.hour.toString().padLeft(2, '0');
    final mm = local.minute.toString().padLeft(2, '0');
    final ss = local.second.toString().padLeft(2, '0');
    return '${local.year}-${local.month.toString().padLeft(2, '0')}-'
        '${local.day.toString().padLeft(2, '0')} $hh:$mm:$ss';
  }
}

class _EmptyView extends StatelessWidget {
  const _EmptyView();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.shield,
            size: 64,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 16),
          const Text('No fire alerts yet'),
          const SizedBox(height: 8),
          Text(
            'Waiting for the controller to report a fire…',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.error});

  final Object? error;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 16),
            const Text('Could not load alerts'),
            const SizedBox(height: 8),
            Text(
              '$error',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
