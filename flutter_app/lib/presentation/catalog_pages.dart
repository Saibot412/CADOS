import 'package:flutter/material.dart';

import '../features/account/account_controller.dart';
import '../features/catalog/record_mutation_controller.dart';
import '../features/catalog/records.dart';
import '../features/workout/workout_import.dart';
import 'session_detail.dart';
import 'workout_editor.dart';
import 'workout_import_picker.dart';

class CatalogPage extends StatelessWidget {
  const CatalogPage({
    super.key,
    required this.account,
    required this.workouts,
    required this.onSelect,
    this.pickWorkoutImport,
  });
  final AccountController account;
  final bool workouts;
  final void Function(WorkoutRecord, String?) onSelect;
  final Future<WorkoutImportSource?> Function()? pickWorkoutImport;
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
          Wrap(
            spacing: 12,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                'Workoutbibliothek',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              FilledButton.icon(
                key: const Key('newWorkout'),
                onPressed: account.busy ? null : () => _openEditor(context),
                icon: const Icon(Icons.add),
                label: const Text('Neu'),
              ),
              OutlinedButton.icon(
                key: const Key('importWorkout'),
                onPressed: account.busy ? null : () => _importWorkout(context),
                icon: const Icon(Icons.file_open_outlined),
                label: const Text('JSON/ZWO importieren'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (catalog.workouts.isEmpty)
            const Text('Keine Workouts in deiner Bibliothek.'),
          for (final workout in catalog.workouts)
            Card(
              child: ExpansionTile(
                title: Text(workout.name),
                trailing: workout.record.shared
                    ? const Icon(Icons.lock_outline)
                    : IconButton(
                        key: Key('deleteWorkout-${workout.record.id}'),
                        tooltip: 'Workout löschen',
                        onPressed: account.busy
                            ? null
                            : () => _deleteWorkout(context, workout),
                        icon: const Icon(Icons.delete_outline),
                      ),
                subtitle: Text(
                  '${workout.duration ~/ 60} min · ${workout.record.shared ? 'Geteilt' : 'Privat'}',
                ),
                children: [
                  Wrap(
                    spacing: 12,
                    runSpacing: 8,
                    children: [
                      FilledButton(
                        onPressed: () => onSelect(workout, null),
                        child: const Text('Vorbereiten'),
                      ),
                      OutlinedButton.icon(
                        key: Key('editWorkout-${workout.record.id}'),
                        onPressed: () => _openEditor(
                          context,
                          workout: workout,
                          copy: workout.record.shared,
                        ),
                        icon: Icon(
                          workout.record.shared ? Icons.copy : Icons.edit,
                        ),
                        label: Text(
                          workout.record.shared ? 'Kopieren' : 'Bearbeiten',
                        ),
                      ),
                      if (!workout.record.shared)
                        TextButton.icon(
                          key: Key('copyWorkout-${workout.record.id}'),
                          onPressed: () => _openEditor(
                            context,
                            workout: workout,
                            copy: true,
                          ),
                          icon: const Icon(Icons.copy),
                          label: const Text('Kopie erstellen'),
                        ),
                    ],
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
                  catalog.workouts.any(
                    (w) => sameUuid(w.record.id, plan.workoutId),
                  )
                  ? FilledButton(
                      onPressed: () => onSelect(
                        catalog.workouts.firstWhere(
                          (w) => sameUuid(w.record.id, plan.workoutId),
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
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) =>
                      SessionDetailPage(session: session, account: account),
                ),
              ),
            ),
        ],
      ],
    );
  }

  Future<void> _openEditor(
    BuildContext context, {
    WorkoutRecord? workout,
    bool copy = false,
  }) => Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) =>
          WorkoutEditorPage(account: account, workout: workout, copy: copy),
    ),
  );

  Future<void> _importWorkout(BuildContext context) async {
    WorkoutImportSource? source;
    try {
      source = await (pickWorkoutImport ?? pickWorkoutImportSource)();
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Die Importdatei konnte nicht gelesen werden.'),
          ),
        );
      }
      return;
    }
    if (source == null || !context.mounted) return;
    final controller = WorkoutImportController(account);
    final success = await controller.import(source.filename, source.content);
    final imported = controller.imported;
    final error = controller.error;
    controller.dispose();
    if (!context.mounted) return;
    if (!success || imported == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error ?? 'Import fehlgeschlagen.')),
      );
      return;
    }
    await _openEditor(context, workout: imported);
  }

  Future<void> _deleteWorkout(
    BuildContext context,
    WorkoutRecord workout,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Workout löschen?'),
        content: Text(
          '„${workout.name}“ wird aus deiner Bibliothek entfernt. Bereits gespeicherte Trainings bleiben erhalten.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Workout löschen'),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;
    final mutation = RecordMutationController(account);
    final success = await mutation.delete(workout.record);
    final message = success
        ? 'Workout wurde gelöscht.'
        : mutation.error ?? 'Workout konnte nicht gelöscht werden.';
    mutation.dispose();
    if (!context.mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }
}
