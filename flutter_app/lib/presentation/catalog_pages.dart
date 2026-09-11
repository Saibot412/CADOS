import 'package:flutter/material.dart';

import '../features/account/account_controller.dart';
import '../features/catalog/records.dart';

class CatalogPage extends StatelessWidget {
  const CatalogPage({
    super.key,
    required this.account,
    required this.workouts,
    required this.onSelect,
  });
  final AccountController account;
  final bool workouts;
  final void Function(WorkoutRecord, String?) onSelect;
  @override
  Widget build(BuildContext context) {
    final catalog = account.catalog;
    if (account.busy && catalog == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (account.user == null) {
      return const Center(
        child: Text(
          'Bitte in Einstellungen anmelden, um deine CADOS-Daten zu laden.',
        ),
      );
    }
    if (catalog == null) {
      return const Center(
        child: Text(
          'Kontodaten nicht verfügbar. Verbindung prüfen und erneut versuchen.',
        ),
      );
    }
    final plans = catalog.upcoming(DateTime.now());
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        if (workouts) ...[
          if (catalog.workouts.isEmpty)
            const Text('Keine Workouts in deiner Bibliothek.'),
          for (final workout in catalog.workouts)
            Card(
              child: ExpansionTile(
                title: Text(workout.name),
                subtitle: Text(
                  '${workout.duration ~/ 60} min · ${workout.record.shared ? 'Geteilt' : 'Privat'}',
                ),
                children: [
                  FilledButton(
                    onPressed: () => onSelect(workout, null),
                    child: const Text('Vorbereiten'),
                  ),
                  if (workout.description != null)
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(workout.description!),
                    ),
                  for (final block in workout.blocks)
                    ListTile(
                      title: Text(
                        block.type == 'steady' ? 'Konstant' : 'Rampe',
                      ),
                      subtitle: Text('${block.duration} Sekunden'),
                    ),
                ],
              ),
            ),
        ] else ...[
          Text(
            account.user!.email,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          if (catalog.profiles.isEmpty) const Text('Kein Profil vorhanden.'),
          for (final profile in catalog.profiles)
            ListTile(
              title: Text(profile.name),
              subtitle: Text('FTP ${profile.ftp ?? '–'} W'),
            ),
          const SizedBox(height: 24),
          Text(
            'Geplantes Training',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          if (plans.isEmpty) const Text('Keine kommenden Einheiten geplant.'),
          for (final plan in plans.take(5))
            ListTile(
              title: Text(plan.workoutName),
              subtitle: Text(plan.date),
              trailing:
                  catalog.workouts.any((w) => w.record.id == plan.workoutId)
                  ? FilledButton(
                      onPressed: () => onSelect(
                        catalog.workouts.firstWhere(
                          (w) => w.record.id == plan.workoutId,
                        ),
                        plan.record.id,
                      ),
                      child: const Text('Vorbereiten'),
                    )
                  : const Text('Workout nicht mehr verfügbar'),
            ),
          const SizedBox(height: 24),
          Text(
            'Trainingshistorie',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          if (catalog.sessions.isEmpty)
            const Text('Keine synchronisierten Trainingseinheiten.'),
          for (final session
              in (catalog.sessions
                    ..sort((a, b) => b.timestamp.compareTo(a.timestamp)))
                  .take(10))
            ListTile(
              title: Text(session.workoutName),
              subtitle: Text(
                '${session.timestamp.toLocal()} · ${session.duration ~/ 60} min · ${session.status == 'completed'
                    ? 'Abgeschlossen'
                    : session.status == 'stopped'
                    ? 'Beendet'
                    : 'Status unbekannt'}',
              ),
            ),
        ],
      ],
    );
  }
}
