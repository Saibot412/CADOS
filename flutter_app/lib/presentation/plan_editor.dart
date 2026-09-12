import 'package:flutter/material.dart';

import '../core/uuid_v4.dart';
import '../features/account/account_controller.dart';
import '../features/calendar/plan_draft.dart';
import '../features/catalog/record_mutation_controller.dart';
import '../features/catalog/records.dart';

class PlanEditorPage extends StatefulWidget {
  const PlanEditorPage({
    super.key,
    required this.account,
    required this.initialDate,
    this.plan,
    this.uuidGenerator = newUuidV4,
    this.pickDate,
  });

  final AccountController account;
  final String initialDate;
  final PlanRecord? plan;
  final String Function() uuidGenerator;
  final Future<DateTime?> Function(BuildContext context, DateTime initial)?
  pickDate;

  @override
  State<PlanEditorPage> createState() => _PlanEditorPageState();
}

class _PlanEditorPageState extends State<PlanEditorPage> {
  late DateTime date = _parseDate(widget.initialDate);
  late String? workoutId = widget.plan?.workoutId;
  late final RecordMutationController mutation = RecordMutationController(
    widget.account,
  );
  late final String targetId = widget.plan?.record.id ?? widget.uuidGenerator();
  bool dirty = false;
  String? localError;

  @override
  void initState() {
    super.initState();
    mutation.addListener(_changed);
    widget.account.addListener(_changed);
  }

  @override
  void dispose() {
    mutation.removeListener(_changed);
    widget.account.removeListener(_changed);
    mutation.dispose();
    super.dispose();
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final workouts =
        widget.account.catalog?.workouts ?? const <WorkoutRecord>[];
    final selectedMatches = workouts
        .where(
          (workout) =>
              workoutId != null && sameUuid(workout.record.id, workoutId!),
        )
        .toList();
    final selectedValue = selectedMatches.length == 1
        ? selectedMatches.single.record.id
        : null;
    final selectedExists = selectedValue != null;
    return PopScope(
      canPop: !dirty && !mutation.busy,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop && !mutation.busy) _confirmDiscard();
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(
            widget.plan == null ? 'Training planen' : 'Planung bearbeiten',
          ),
        ),
        body: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Text('Datum', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              key: const Key('planDate'),
              onPressed: mutation.busy ? null : _chooseDate,
              icon: const Icon(Icons.calendar_month),
              label: Text(_iso(date)),
            ),
            const SizedBox(height: 20),
            DropdownButtonFormField<String>(
              key: const Key('planWorkout'),
              initialValue: selectedValue,
              decoration: const InputDecoration(
                labelText: 'Workout',
                border: OutlineInputBorder(),
              ),
              items: [
                for (final workout in workouts)
                  DropdownMenuItem(
                    value: workout.record.id,
                    child: Text(workout.name),
                  ),
              ],
              onChanged: mutation.busy
                  ? null
                  : (value) => setState(() {
                      workoutId = value;
                      dirty = true;
                      localError = null;
                    }),
            ),
            if (!selectedExists && widget.plan != null) ...[
              const SizedBox(height: 8),
              Text(
                'Das bisherige Workout ist nicht mehr verfügbar. Bitte ein anderes auswählen.',
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            if (workouts.isEmpty) ...[
              const SizedBox(height: 8),
              const Text(
                'Zum Planen ist ein verfügbares Workout erforderlich.',
              ),
            ],
            const SizedBox(height: 24),
            if (mutation.busy) const LinearProgressIndicator(),
            if (localError != null || mutation.error != null)
              Text(
                localError ?? mutation.error!,
                key: const Key('planError'),
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              children: [
                FilledButton(
                  key: const Key('savePlan'),
                  onPressed: mutation.busy || workouts.isEmpty ? null : _save,
                  child: const Text('Planung speichern'),
                ),
                TextButton(
                  onPressed: mutation.busy ? null : _cancel,
                  child: const Text('Abbrechen'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _chooseDate() async {
    final chosen =
        await (widget.pickDate?.call(context, date) ??
            showDatePicker(
              context: context,
              initialDate: date,
              firstDate: DateTime(1),
              lastDate: DateTime(9999, 12, 31),
            ));
    if (chosen != null && mounted) {
      setState(() {
        date = DateTime(chosen.year, chosen.month, chosen.day);
        dirty = true;
        localError = null;
      });
    }
  }

  Future<void> _save() async {
    setState(() => localError = null);
    final workouts =
        widget.account.catalog?.workouts ?? const <WorkoutRecord>[];
    final selected = workouts
        .where(
          (workout) =>
              workoutId != null && sameUuid(workout.record.id, workoutId!),
        )
        .toList();
    if (selected.length != 1) {
      setState(() => localError = 'Bitte ein verfügbares Workout auswählen.');
      return;
    }
    Map<String, dynamic> payload;
    try {
      final draft = widget.plan == null
          ? PlanDraft(
              date: _iso(date),
              workoutId: selected.single.record.id,
              workoutName: selected.single.name,
            )
          : PlanDraft.fromRecord(widget.plan!)
                .updateDate(date)
                .updateWorkout(selected.single);
      payload = draft.toJson();
    } on FormatException catch (error) {
      setState(() => localError = error.message);
      return;
    }
    final success = widget.plan == null
        ? await mutation.create(id: targetId, kind: 'plan', payload: payload)
        : await mutation.update(widget.plan!.record, payload);
    if (success && mounted) {
      setState(() => dirty = false);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) Navigator.pop(context);
      });
    }
  }

  Future<void> _cancel() async {
    if (!dirty || await _discardConfirmed()) {
      if (mounted) Navigator.pop(context);
    }
  }

  Future<void> _confirmDiscard() async {
    if (await _discardConfirmed() && mounted) Navigator.pop(context);
  }

  Future<bool> _discardConfirmed() async =>
      await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Änderungen verwerfen?'),
          content: const Text(
            'Nicht gespeicherte Kalenderänderungen gehen verloren.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Weiter bearbeiten'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Verwerfen'),
            ),
          ],
        ),
      ) ??
      false;

  static DateTime _parseDate(String value) {
    if (!isLocalCalendarDate(value)) {
      throw const FormatException('Ungültiges Kalenderdatum.');
    }
    final parts = value.split('-');
    return DateTime(
      int.parse(parts[0]),
      int.parse(parts[1]),
      int.parse(parts[2]),
    );
  }

  static String _iso(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';
}
