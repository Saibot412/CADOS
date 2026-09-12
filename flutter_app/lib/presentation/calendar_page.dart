import 'package:flutter/material.dart';

import '../features/account/account_controller.dart';
import '../features/catalog/record_mutation_controller.dart';
import '../features/catalog/records.dart';
import 'plan_editor.dart';
import 'session_detail.dart';

class CalendarPage extends StatefulWidget {
  const CalendarPage({
    super.key,
    required this.account,
    required this.onSelect,
    this.now = DateTime.now,
  });

  final AccountController account;
  final void Function(WorkoutRecord workout, String planId) onSelect;
  final DateTime Function() now;

  @override
  State<CalendarPage> createState() => _CalendarPageState();
}

class _CalendarPageState extends State<CalendarPage> {
  late DateTime selected = _dateOnly(widget.now());
  late DateTime month = DateTime(selected.year, selected.month);

  @override
  Widget build(BuildContext context) {
    final catalog = widget.account.catalog;
    if (widget.account.busy && catalog == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (widget.account.user == null) {
      return const Center(
        child: Text(
          'Bitte in Einstellungen anmelden, um deinen Kalender zu laden.',
        ),
      );
    }
    if (catalog == null) {
      return const Center(
        child: Text('Kalender nicht verfügbar. Verbindung prüfen.'),
      );
    }
    final calendar = _calendar(context, catalog);
    final agenda = _agenda(context, catalog);
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth >= 900) {
          return SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(flex: 3, child: calendar),
                const SizedBox(width: 24),
                Expanded(flex: 2, child: agenda),
              ],
            ),
          );
        }
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [calendar, const SizedBox(height: 24), agenda],
        );
      },
    );
  }

  Widget _calendar(BuildContext context, Catalog catalog) {
    final first = DateTime(month.year, month.month);
    final leading = (first.weekday - DateTime.monday) % 7;
    final days = DateTime(month.year, month.month + 1, 0).day;
    final plans = catalog.active('plan').map(PlanRecord.new).toList();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Row(
              children: [
                IconButton(
                  key: const Key('previousMonth'),
                  tooltip: 'Vorheriger Monat',
                  onPressed: month.year == 1 && month.month == 1
                      ? null
                      : () => _changeMonth(-1),
                  icon: const Icon(Icons.chevron_left),
                ),
                Expanded(
                  child: Text(
                    _monthLabel(month),
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                IconButton(
                  key: const Key('nextMonth'),
                  tooltip: 'Nächster Monat',
                  onPressed: month.year == 9999 && month.month == 12
                      ? null
                      : () => _changeMonth(1),
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
            Row(
              children: [
                for (final day in const [
                  'Mo',
                  'Di',
                  'Mi',
                  'Do',
                  'Fr',
                  'Sa',
                  'So',
                ])
                  Expanded(child: Center(child: Text(day))),
              ],
            ),
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 7,
                childAspectRatio: 1.05,
              ),
              itemCount: leading + days,
              itemBuilder: (context, index) {
                if (index < leading) return const SizedBox.shrink();
                final date = DateTime(
                  month.year,
                  month.month,
                  index - leading + 1,
                );
                final iso = _iso(date);
                final count = plans.where((plan) => plan.date == iso).length;
                final isSelected = DateUtils.isSameDay(date, selected);
                return Padding(
                  padding: const EdgeInsets.all(2),
                  child: Semantics(
                    label: '$iso, $count geplante Einheiten',
                    button: true,
                    selected: isSelected,
                    child: InkWell(
                      key: Key('calendarDay-$iso'),
                      borderRadius: BorderRadius.circular(12),
                      onTap: () => setState(() => selected = date),
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          color: isSelected
                              ? Theme.of(context).colorScheme.primaryContainer
                              : null,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text('${date.day}'),
                            if (count > 0)
                              Badge(
                                key: Key('calendarCount-$iso'),
                                label: Text('$count'),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _agenda(BuildContext context, Catalog catalog) {
    final iso = _iso(selected);
    final plans =
        catalog
            .active('plan')
            .map(PlanRecord.new)
            .where((p) => p.date == iso)
            .toList()
          ..sort((a, b) => a.workoutName.compareTo(b.workoutName));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(iso, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 8),
        FilledButton.icon(
          key: const Key('newPlan'),
          onPressed: widget.account.busy
              ? null
              : () => _openEditor(context, date: iso),
          icon: const Icon(Icons.add),
          label: const Text('Training planen'),
        ),
        const SizedBox(height: 12),
        if (plans.isEmpty) const Text('Keine Einheiten an diesem Tag.'),
        for (final plan in plans) _planCard(context, catalog, plan),
        const SizedBox(height: 24),
        Text('Profil', style: Theme.of(context).textTheme.titleLarge),
        if (catalog.profiles.isEmpty)
          const Text('Kein Profil vorhanden.')
        else
          for (final profile in catalog.profiles)
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(profile.name),
              subtitle: Text('FTP ${profile.ftp ?? '–'} W'),
            ),
        const SizedBox(height: 16),
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
            key: Key('calendarSession-${session.record.id}'),
            contentPadding: EdgeInsets.zero,
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
                builder: (_) => SessionDetailPage(
                  session: session,
                  account: widget.account,
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _planCard(BuildContext context, Catalog catalog, PlanRecord plan) {
    final workouts = catalog.workouts
        .where((w) => sameUuid(w.record.id, plan.workoutId))
        .toList();
    final workout = workouts.length == 1 ? workouts.single : null;
    final completed = catalog.sessions.any(
      (session) =>
          session.status == 'completed' &&
          session.planId != null &&
          sameUuid(session.planId!, plan.record.id),
    );
    final past = plan.date.compareTo(_iso(_dateOnly(widget.now()))) < 0;
    return Card(
      key: Key('calendarPlan-${plan.record.id}'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              plan.workoutName,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (completed)
              const Text('Abgeschlossen', key: Key('planCompleted'))
            else if (past)
              const Text('Datum liegt in der Vergangenheit')
            else if (workout == null)
              const Text('Workout nicht mehr verfügbar')
            else
              const Text('Bereit'),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                FilledButton(
                  key: Key('startPlan-${plan.record.id}'),
                  onPressed: completed || past || workout == null
                      ? null
                      : () => widget.onSelect(workout, plan.record.id),
                  child: const Text('Vorbereiten'),
                ),
                OutlinedButton(
                  key: Key('editPlan-${plan.record.id}'),
                  onPressed: widget.account.busy
                      ? null
                      : () => _openEditor(context, plan: plan, date: plan.date),
                  child: const Text('Bearbeiten'),
                ),
                IconButton(
                  key: Key('deletePlan-${plan.record.id}'),
                  tooltip: 'Planung entfernen',
                  onPressed: widget.account.busy
                      ? null
                      : () => _delete(context, plan),
                  icon: const Icon(Icons.delete_outline),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openEditor(
    BuildContext context, {
    PlanRecord? plan,
    required String date,
  }) => Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => PlanEditorPage(
        account: widget.account,
        initialDate: date,
        plan: plan,
      ),
    ),
  );

  Future<void> _delete(BuildContext context, PlanRecord plan) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Planung entfernen?'),
        content: Text('„${plan.workoutName}“ wird aus dem Kalender entfernt.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Entfernen'),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;
    final mutation = RecordMutationController(widget.account);
    final success = await mutation.delete(plan.record);
    final message = success
        ? 'Planung wurde entfernt.'
        : mutation.error ?? 'Planung konnte nicht entfernt werden.';
    mutation.dispose();
    if (context.mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(message)));
    }
  }

  void _changeMonth(int offset) {
    final next = DateTime(month.year, month.month + offset);
    final lastDay = DateTime(next.year, next.month + 1, 0).day;
    setState(() {
      month = next;
      selected = DateTime(
        next.year,
        next.month,
        selected.day > lastDay ? lastDay : selected.day,
      );
    });
  }

  static DateTime _dateOnly(DateTime value) =>
      DateTime(value.year, value.month, value.day);
  static String _iso(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';
  static String _monthLabel(DateTime value) =>
      '${const ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'][value.month - 1]} ${value.year}';
}
