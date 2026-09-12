import 'package:flutter/material.dart';

import '../features/session/workout_session_controller.dart';
import '../features/session/session_sync_controller.dart';
import '../features/workout/workout_engine.dart';
import 'device_settings.dart';

String workoutStateLabel(WorkoutState state) => switch (state) {
  WorkoutState.ready => 'Bereit zur Vorbereitung',
  WorkoutState.waitingForPedal => 'Warte auf neue positive Leistung',
  WorkoutState.running => 'Training läuft',
  WorkoutState.paused => 'Pausiert – ausdrücklich fortsetzen',
  WorkoutState.stopped => 'Training beendet',
  WorkoutState.completed => 'Workout abgeschlossen',
};
String trainingTime(num seconds) =>
    '${seconds.floor() ~/ 60}:${(seconds.floor() % 60).toString().padLeft(2, '0')}';

class TrainingScreen extends StatelessWidget {
  const TrainingScreen({super.key, required this.session, required this.sync});
  final WorkoutSessionController session;
  final SessionSyncController sync;
  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: Listenable.merge([session, sync]),
    builder: (context, _) {
      final engine = session.engine;
      final workout = engine?.workout;
      final metrics = session.metrics;
      final ftpTest = session.completedFtpTest;
      final enabled = !session.busy;
      return ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text(
            session.data?.workoutPayload['name'] as String? ??
                session.selected?.name ??
                workout?.name ??
                'Kein Workout ausgewählt',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          Text(workoutStateLabel(session.state)),
          Text('Trainer: ${connectionLabel(session.trainer.connection.phase)}'),
          if (session.planId != null)
            const Text('Mit geplanter Kalendereinheit verknüpft'),
          if (session.readiness != null) Text(session.readiness!),
          if (session.error != null)
            Text(
              session.error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          SwitchListTile(
            key: const Key('adaptiveErgToggle'),
            contentPadding: EdgeInsets.zero,
            value: session.adaptiveErgAllowed
                ? session.adaptiveErgPreferred
                : false,
            onChanged:
                enabled && session.initialized && session.adaptiveErgAllowed
                ? session.setAdaptiveErg
                : null,
            title: const Text('Adaptive ERG-Entlastung'),
            subtitle: Text(
              session.adaptiveErgAllowed
                  ? 'Optional: senkt das Trainerziel bei anhaltend niedriger Kadenz '
                        'langsam um höchstens 10 %. Standard-ERG bleibt bei ausgeschaltetem Schalter unverändert.'
                  : 'Für FTP-Rampentests ist adaptive Entlastung aus Sicherheitsgründen '
                        'vorübergehend deaktiviert; die Einstellung bleibt gespeichert.',
            ),
          ),
          if (!session.initialized)
            TextButton(
              onPressed: enabled ? session.initialize : null,
              child: const Text('Trainingsspeicher erneut prüfen'),
            ),
          if (session.recovery != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Unterbrochene Einheit gefunden'),
                    Text(
                      '${session.recovery!.workoutPayload['name']} · ${trainingTime(session.recovery!.elapsed)} gefahren',
                    ),
                    const Text(
                      'Wiederherstellen lädt die Einheit pausiert. Es werden keine Trainerbefehle gesendet.',
                    ),
                    Wrap(
                      spacing: 12,
                      children: [
                        FilledButton(
                          onPressed: enabled ? session.recover : null,
                          child: const Text('Wiederherstellen'),
                        ),
                        TextButton(
                          onPressed: enabled
                              ? () async {
                                  final discard = await showDialog<bool>(
                                    context: context,
                                    builder: (context) => AlertDialog(
                                      title: const Text('Sicherung verwerfen?'),
                                      content: const Text(
                                        'Die unterbrochene Einheit wird unwiderruflich gelöscht.',
                                      ),
                                      actions: [
                                        TextButton(
                                          onPressed: () =>
                                              Navigator.pop(context, false),
                                          child: const Text('Abbrechen'),
                                        ),
                                        TextButton(
                                          onPressed: () =>
                                              Navigator.pop(context, true),
                                          child: const Text('Verwerfen'),
                                        ),
                                      ],
                                    ),
                                  );
                                  if (discard == true) {
                                    await session.discardRecovery();
                                  }
                                }
                              : null,
                          child: const Text('Verwerfen'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 20),
          Wrap(
            spacing: 24,
            runSpacing: 16,
            children: [
              _metric(
                'Leistung',
                session.watts == null ? '–' : '${session.watts} W',
              ),
              _metric(
                'Vorgabe',
                session.prescribedTarget == null
                    ? '–'
                    : '${session.prescribedTarget} W',
              ),
              _metric(
                'Effektives Trainerziel',
                session.effectiveTrainerTarget == null
                    ? '–'
                    : '${session.effectiveTrainerTarget} W',
              ),
              if (session.adaptiveErgActive)
                _metric('ERG-Entlastung', '${session.adaptiveReliefWatts} W'),
              _metric(
                'Kadenz',
                session.cadence == null
                    ? '–'
                    : '${session.cadence!.toStringAsFixed(1)} rpm',
              ),
              _metric(
                'Herzfrequenz',
                session.bpm == null ? '–' : '${session.bpm} bpm',
              ),
              _metric(
                'Gefahren',
                engine == null ? '–' : trainingTime(engine.elapsed),
              ),
              _metric(
                'Verbleibend',
                engine == null
                    ? '–'
                    : trainingTime(workout!.duration - engine.elapsed),
              ),
            ],
          ),
          if (metrics != null) ...[
            const SizedBox(height: 20),
            Text(
              'Trainingsmetriken',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 24,
              runSpacing: 16,
              children: [
                _metric('Ø Leistung', '${metrics['avg_watts']} W'),
                _metric('Max. Leistung', '${metrics['max_watts']} W'),
                _metric('Normalized Power', '${metrics['normalized_power']} W'),
                _metric(
                  'Intensity Factor',
                  _decimal(metrics['intensity_factor'], 2),
                ),
                _metric('TSS', _decimal(metrics['tss'], 1)),
                _metric('Arbeit', '${_decimal(metrics['work_kj'], 1)} kJ'),
                _metric('Beste Minute', '${metrics['best_minute_watts']} W'),
                _metric('Ø Kadenz', '${metrics['avg_cadence']} rpm'),
                _metric('Max. Kadenz', '${metrics['max_cadence']} rpm'),
                _metric('Ø Herzfrequenz', '${metrics['avg_heart_rate']} bpm'),
                _metric(
                  'Max. Herzfrequenz',
                  '${metrics['max_heart_rate']} bpm',
                ),
              ],
            ),
          ],
          if (ftpTest != null) ...[
            const SizedBox(height: 20),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'FTP-Rampentest',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    if (ftpTest['eligible'] == true) ...[
                      Text(
                        'Beste gemessene Minute: ${ftpTest['best_minute_watts']} W',
                      ),
                      Text('Geschätzte FTP: ${ftpTest['estimated_ftp']} W'),
                      const Text(
                        'Die Profiländerung erfolgt erst nach Bestätigung.',
                      ),
                    ] else
                      Text(
                        ftpTest['reason']?.toString() ??
                            'Keine belastbare FTP-Auswertung verfügbar.',
                      ),
                  ],
                ),
              ),
            ),
          ],
          if (workout != null) ...[
            const SizedBox(height: 20),
            Text(
              'Aktueller Block: ${workout.blocks[engine!.blockIndex].label}',
            ),
            Text(
              engine.blockIndex + 1 < workout.blocks.length
                  ? 'Nächster Block: ${workout.blocks[engine.blockIndex + 1].label}'
                  : 'Kein weiterer Block',
            ),
          ],
          const SizedBox(height: 20),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              FilledButton(
                key: const Key('startWorkout'),
                onPressed:
                    enabled && !session.hasSession && session.readiness == null
                    ? session.start
                    : null,
                child: const Text('Starten'),
              ),
              OutlinedButton(
                onPressed:
                    enabled &&
                        [
                          WorkoutState.running,
                          WorkoutState.waitingForPedal,
                        ].contains(session.state)
                    ? session.pause
                    : null,
                child: const Text('Pausieren'),
              ),
              FilledButton.tonal(
                onPressed:
                    enabled &&
                        session.hasSession &&
                        session.state == WorkoutState.paused &&
                        session.readiness == null
                    ? session.resume
                    : null,
                child: const Text('Fortsetzen'),
              ),
              OutlinedButton(
                key: const Key('stopWorkout'),
                onPressed: enabled && session.hasSession ? session.stop : null,
                child: const Text('Beenden / Speichern'),
              ),
              OutlinedButton(
                onPressed: enabled && session.active
                    ? () => session.adjust(-5)
                    : null,
                child: const Text('−5 W'),
              ),
              OutlinedButton(
                onPressed: enabled && session.active
                    ? () => session.adjust(5)
                    : null,
                child: const Text('+5 W'),
              ),
            ],
          ),
          const Divider(height: 40),
          Text(
            !sync.loaded
                ? 'Trainingsspeicher noch nicht verfügbar.'
                : sync.pending == 0
                ? 'Keine ausstehenden Session-Uploads.'
                : '${sync.pending} Einheit(en) lokal gespeichert; Synchronisierung ausstehend.',
          ),
          if (sync.error != null) Text(sync.error!),
          TextButton(
            onPressed: sync.busy ? null : sync.retry,
            child: const Text('Synchronisierung erneut versuchen'),
          ),
        ],
      );
    },
  );
  Widget _metric(String label, String value) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label),
      Text(value, style: const TextStyle(fontSize: 24)),
    ],
  );

  String _decimal(num? value, int places) =>
      value == null ? '–' : value.toStringAsFixed(places);
}
