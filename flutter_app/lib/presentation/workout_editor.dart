import 'package:flutter/material.dart';

import '../core/uuid_v4.dart';
import '../features/account/account_controller.dart';
import '../features/catalog/record_mutation_controller.dart';
import '../features/catalog/records.dart';
import '../features/workout/workout.dart';
import '../features/workout/workout_draft.dart';
import '../features/workout/workout_parser.dart';
import 'workout_preview.dart';

class WorkoutEditorPage extends StatefulWidget {
  const WorkoutEditorPage({
    super.key,
    required this.account,
    this.workout,
    this.copy = false,
    this.uuidGenerator = newUuidV4,
  });

  final AccountController account;
  final WorkoutRecord? workout;
  final bool copy;
  final String Function() uuidGenerator;

  @override
  State<WorkoutEditorPage> createState() => _WorkoutEditorPageState();
}

class _WorkoutEditorPageState extends State<WorkoutEditorPage> {
  late WorkoutDraft draft;
  late final TextEditingController name;
  late final TextEditingController description;
  late final RecordMutationController mutation = RecordMutationController(
    widget.account,
  );
  late final String targetId =
      widget.workout == null || widget.copy || widget.workout!.record.shared
      ? widget.uuidGenerator()
      : widget.workout!.record.id;
  late WorkoutRecord? current = widget.workout;
  late bool copyMode = widget.copy || widget.workout?.record.shared == true;
  bool dirty = false;
  String? localError;
  String? status;
  final List<int> blockIds = [];
  int nextBlockId = 0;

  bool get createsCopy => current != null && copyMode;

  @override
  void initState() {
    super.initState();
    if (widget.workout == null) {
      draft = WorkoutDraft(
        name: 'Neues Workout',
        blocks: [SteadyBlockDraft(durationSec: 300, targetWatts: 150)],
      );
    } else {
      draft = WorkoutDraft.fromJson(
        Map<String, dynamic>.from(widget.workout!.record.payload),
      );
    }
    blockIds.addAll(List.generate(draft.blocks.length, (_) => nextBlockId++));
    final initialName = createsCopy ? '${draft.name} (Kopie)' : draft.name;
    name = TextEditingController(text: initialName);
    description = TextEditingController(
      text: draft.metadata['description'] as String? ?? '',
    );
    mutation.addListener(_mutationChanged);
  }

  @override
  void dispose() {
    mutation.removeListener(_mutationChanged);
    mutation.dispose();
    name.dispose();
    description.dispose();
    super.dispose();
  }

  void _mutationChanged() {
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !dirty || mutation.saved,
    onPopInvokedWithResult: (didPop, _) {
      if (!didPop) _confirmDiscard();
    },
    child: Scaffold(
      appBar: AppBar(
        title: Text(
          current == null
              ? 'Workout erstellen'
              : createsCopy
              ? 'Workout kopieren'
              : 'Workout bearbeiten',
        ),
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final editor = _editorColumn(context);
          final preview = _previewColumn(context);
          if (constraints.maxWidth >= 1000) {
            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: editor),
                const VerticalDivider(width: 1),
                SizedBox(width: 380, child: preview),
              ],
            );
          }
          return editor;
        },
      ),
    ),
  );

  Widget _editorColumn(BuildContext context) => ListView(
    padding: const EdgeInsets.all(24),
    children: [
      if (createsCopy)
        const Card(
          child: ListTile(
            leading: Icon(Icons.lock_outline),
            title: Text('Geteiltes Workout ist schreibgeschützt'),
            subtitle: Text('Beim Speichern wird eine private Kopie erstellt.'),
          ),
        ),
      TextField(
        key: const Key('workoutName'),
        controller: name,
        textInputAction: TextInputAction.next,
        decoration: const InputDecoration(
          labelText: 'Workoutname',
          border: OutlineInputBorder(),
        ),
        onChanged: (_) => _markDirty(),
      ),
      const SizedBox(height: 12),
      TextField(
        key: const Key('workoutDescription'),
        controller: description,
        maxLines: 2,
        decoration: const InputDecoration(
          labelText: 'Beschreibung (optional)',
          border: OutlineInputBorder(),
        ),
        onChanged: (_) => _markDirty(),
      ),
      const SizedBox(height: 24),
      Row(
        children: [
          Expanded(
            child: Text(
              'Trainingsblöcke',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
          ),
          Text('${draft.blocks.length} / 2000'),
        ],
      ),
      const SizedBox(height: 8),
      for (var index = 0; index < draft.blocks.length; index++)
        _blockCard(context, index, draft.blocks[index]),
      Wrap(
        spacing: 12,
        runSpacing: 8,
        children: [
          OutlinedButton.icon(
            key: const Key('addSteadyBlock'),
            onPressed: draft.blocks.length >= 2000
                ? null
                : () => _addBlock(
                    SteadyBlockDraft(durationSec: 300, targetWatts: 150),
                  ),
            icon: const Icon(Icons.add),
            label: const Text('Konstanten Block hinzufügen'),
          ),
          OutlinedButton.icon(
            key: const Key('addRampBlock'),
            onPressed: draft.blocks.length >= 2000
                ? null
                : () => _addBlock(
                    RampBlockDraft(
                      durationSec: 300,
                      startWatts: 100,
                      endWatts: 200,
                    ),
                  ),
            icon: const Icon(Icons.trending_up),
            label: const Text('Rampe hinzufügen'),
          ),
        ],
      ),
      if (MediaQuery.sizeOf(context).width < 1000) ...[
        const SizedBox(height: 24),
        _previewColumn(context),
      ],
      const SizedBox(height: 24),
      if (mutation.busy) const LinearProgressIndicator(),
      if (localError != null || mutation.error != null)
        Text(
          localError ?? mutation.error!,
          key: const Key('workoutError'),
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
      if (status != null) Text(status!, key: const Key('workoutStatus')),
      const SizedBox(height: 8),
      Wrap(
        spacing: 12,
        children: [
          FilledButton.icon(
            key: const Key('saveWorkout'),
            onPressed: mutation.busy ? null : _save,
            icon: const Icon(Icons.save_outlined),
            label: Text(createsCopy ? 'Private Kopie speichern' : 'Speichern'),
          ),
          TextButton(
            onPressed: mutation.busy ? null : _cancel,
            child: const Text('Abbrechen'),
          ),
        ],
      ),
      const SizedBox(height: 24),
    ],
  );

  Widget _previewColumn(BuildContext context) => Padding(
    padding: const EdgeInsets.all(16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Vorschau', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        WorkoutPreview(workout: _resolvedWorkout()),
        Text(
          '${draft.blocks.fold<int>(0, (sum, block) => sum + block.durationSec) ~/ 60} min',
        ),
      ],
    ),
  );

  Widget _blockCard(BuildContext context, int index, WorkoutBlockDraft block) =>
      Card(
        key: Key('workoutBlock-$index'),
        margin: const EdgeInsets.only(bottom: 12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    'Block ${index + 1}',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const Spacer(),
                  IconButton(
                    key: Key('moveBlockUp-$index'),
                    tooltip: 'Nach oben',
                    onPressed: index == 0
                        ? null
                        : () => _reorderBlock(index, index - 1),
                    icon: const Icon(Icons.arrow_upward),
                  ),
                  IconButton(
                    key: Key('moveBlockDown-$index'),
                    tooltip: 'Nach unten',
                    onPressed: index == draft.blocks.length - 1
                        ? null
                        : () => _reorderBlock(index, index + 1),
                    icon: const Icon(Icons.arrow_downward),
                  ),
                  IconButton(
                    key: Key('removeBlock-$index'),
                    tooltip: 'Block entfernen',
                    onPressed: () => _removeBlock(index),
                    icon: const Icon(Icons.delete_outline),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  _field(
                    key: Key('blockLabel-${blockIds[index]}'),
                    width: 210,
                    initial: block.label ?? '',
                    label: 'Bezeichnung',
                    onChanged: (value) => _updateCommon(
                      index,
                      label: value.trim().isEmpty ? null : value,
                    ),
                  ),
                  _field(
                    key: Key('blockDuration-${blockIds[index]}'),
                    width: 150,
                    initial: block.durationSec.toString(),
                    label: 'Dauer (Sek.)',
                    numeric: true,
                    onChanged: (value) => _updateCommon(
                      index,
                      duration: int.tryParse(value) ?? 0,
                    ),
                  ),
                  _field(
                    key: Key('blockCadence-${blockIds[index]}'),
                    width: 160,
                    initial: block.targetCadence?.toString() ?? '',
                    label: 'Kadenz (optional)',
                    numeric: true,
                    onChanged: (value) => _updateCommon(
                      index,
                      cadence: value.trim().isEmpty
                          ? null
                          : int.tryParse(value) ?? 0,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              if (block is SteadyBlockDraft) _steadyFields(index, block),
              if (block is RampBlockDraft) _rampFields(index, block),
            ],
          ),
        ),
      );

  Widget _steadyFields(int index, SteadyBlockDraft block) => Wrap(
    spacing: 12,
    runSpacing: 12,
    crossAxisAlignment: WrapCrossAlignment.center,
    children: [
      _targetMode(
        key: Key('steadyMode-$index'),
        ftp: block.usesFtpTarget,
        onChanged: (ftp) => _setBlock(
          index,
          ftp
              ? block.copyWith(targetPctFtp: block.targetPctFtp ?? .75)
              : block.copyWith(
                  targetPctFtp: null,
                  targetWatts: block.targetWatts ?? 150,
                ),
        ),
      ),
      _field(
        key: Key('steadyTarget-${blockIds[index]}'),
        width: 170,
        initial: block.usesFtpTarget
            ? _number(block.targetPctFtp! * 100)
            : block.targetWatts?.toString() ?? '',
        label: block.usesFtpTarget ? 'Ziel (% FTP)' : 'Ziel (W)',
        numeric: true,
        decimal: block.usesFtpTarget,
        onChanged: (value) => _setBlock(
          index,
          block.usesFtpTarget
              ? block.copyWith(targetPctFtp: (_double(value) ?? 0) / 100)
              : block.copyWith(targetWatts: int.tryParse(value) ?? 0),
        ),
      ),
    ],
  );

  Widget _rampFields(int index, RampBlockDraft block) => Wrap(
    spacing: 12,
    runSpacing: 12,
    crossAxisAlignment: WrapCrossAlignment.center,
    children: [
      _targetMode(
        key: Key('rampStartMode-$index'),
        ftp: block.usesFtpStart,
        onChanged: (ftp) => _setBlock(
          index,
          ftp
              ? block.copyWith(startPctFtp: block.startPctFtp ?? .5)
              : block.copyWith(
                  startPctFtp: null,
                  startWatts: block.startWatts ?? 100,
                ),
        ),
      ),
      _field(
        key: Key('rampStart-${blockIds[index]}'),
        width: 160,
        initial: block.usesFtpStart
            ? _number(block.startPctFtp! * 100)
            : block.startWatts?.toString() ?? '',
        label: block.usesFtpStart ? 'Start (% FTP)' : 'Start (W)',
        numeric: true,
        decimal: block.usesFtpStart,
        onChanged: (value) => _setBlock(
          index,
          block.usesFtpStart
              ? block.copyWith(startPctFtp: (_double(value) ?? 0) / 100)
              : block.copyWith(startWatts: int.tryParse(value) ?? 0),
        ),
      ),
      _targetMode(
        key: Key('rampEndMode-$index'),
        ftp: block.usesFtpEnd,
        onChanged: (ftp) => _setBlock(
          index,
          ftp
              ? block.copyWith(endPctFtp: block.endPctFtp ?? 1)
              : block.copyWith(
                  endPctFtp: null,
                  endWatts: block.endWatts ?? 200,
                ),
        ),
      ),
      _field(
        key: Key('rampEnd-${blockIds[index]}'),
        width: 160,
        initial: block.usesFtpEnd
            ? _number(block.endPctFtp! * 100)
            : block.endWatts?.toString() ?? '',
        label: block.usesFtpEnd ? 'Ende (% FTP)' : 'Ende (W)',
        numeric: true,
        decimal: block.usesFtpEnd,
        onChanged: (value) => _setBlock(
          index,
          block.usesFtpEnd
              ? block.copyWith(endPctFtp: (_double(value) ?? 0) / 100)
              : block.copyWith(endWatts: int.tryParse(value) ?? 0),
        ),
      ),
    ],
  );

  Widget _targetMode({
    required Key key,
    required bool ftp,
    required ValueChanged<bool> onChanged,
  }) => SegmentedButton<bool>(
    key: key,
    segments: const [
      ButtonSegment(value: false, label: Text('Watt')),
      ButtonSegment(value: true, label: Text('% FTP')),
    ],
    selected: {ftp},
    onSelectionChanged: (selection) => onChanged(selection.single),
  );

  Widget _field({
    required Key key,
    required double width,
    required String initial,
    required String label,
    required ValueChanged<String> onChanged,
    bool numeric = false,
    bool decimal = false,
  }) => SizedBox(
    width: width,
    child: TextFormField(
      key: key,
      initialValue: initial,
      keyboardType: numeric
          ? TextInputType.numberWithOptions(decimal: decimal)
          : TextInputType.text,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
      onChanged: onChanged,
    ),
  );

  void _updateCommon(
    int index, {
    int? duration,
    Object? label = _notSet,
    Object? cadence = _notSet,
  }) {
    final block = draft.blocks[index];
    if (block is SteadyBlockDraft) {
      _setBlock(
        index,
        block.copyWith(
          durationSec: duration,
          label: identical(label, _notSet) ? block.label : label,
          targetCadence: identical(cadence, _notSet)
              ? block.targetCadence
              : cadence,
        ),
      );
    } else if (block is RampBlockDraft) {
      _setBlock(
        index,
        block.copyWith(
          durationSec: duration,
          label: identical(label, _notSet) ? block.label : label,
          targetCadence: identical(cadence, _notSet)
              ? block.targetCadence
              : cadence,
        ),
      );
    }
  }

  void _addBlock(WorkoutBlockDraft block) {
    blockIds.add(nextBlockId++);
    _replaceDraft(draft.addBlock(block));
  }

  void _removeBlock(int index) {
    blockIds.removeAt(index);
    _replaceDraft(draft.removeBlock(index));
  }

  void _reorderBlock(int from, int to) {
    final id = blockIds.removeAt(from);
    blockIds.insert(to, id);
    _replaceDraft(draft.reorderBlock(from, to));
  }

  void _setBlock(int index, WorkoutBlockDraft block) =>
      _replaceDraft(draft.updateBlock(index, block));

  void _replaceDraft(WorkoutDraft value) {
    setState(() {
      draft = value;
      dirty = true;
      localError = null;
      status = null;
    });
  }

  void _markDirty() {
    if (!dirty) setState(() => dirty = true);
  }

  Workout? _resolvedWorkout() {
    final ftp = widget.account.catalog?.profiles
        .map((profile) => profile.ftp)
        .whereType<int>()
        .firstOrNull;
    if (ftp == null) return null;
    try {
      return WorkoutParser.parse(draft.toJson(), ftp: ftp);
    } catch (_) {
      return null;
    }
  }

  Future<void> _save() async {
    setState(() {
      localError = null;
      status = null;
    });
    Map<String, dynamic> payload;
    try {
      final metadata = Map<String, dynamic>.from(draft.metadata);
      final descriptionValue = description.text.trim();
      if (descriptionValue.isEmpty) {
        metadata.remove('description');
      } else {
        metadata['description'] = descriptionValue;
      }
      payload = draft
          .copyWith(name: name.text.trim(), metadata: metadata)
          .toJson();
    } on FormatException catch (error) {
      setState(() => localError = error.message);
      return;
    }
    final wasCreating = current == null || createsCopy;
    final success = wasCreating
        ? await mutation.create(id: targetId, kind: 'workout', payload: payload)
        : await mutation.update(current!.record, payload);
    if (!mounted || !success) return;
    current = widget.account.catalog!.workouts.singleWhere(
      (workout) => workout.record.id == targetId,
    );
    draft = WorkoutDraft.fromJson(
      Map<String, dynamic>.from(current!.record.payload),
    );
    blockIds
      ..clear()
      ..addAll(List.generate(draft.blocks.length, (_) => nextBlockId++));
    name.text = draft.name;
    description.text = draft.metadata['description'] as String? ?? '';
    copyMode = false;
    setState(() {
      dirty = false;
      status = wasCreating
          ? 'Workout wurde vom Server angelegt.'
          : 'Workout wurde vom Server gespeichert.';
    });
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
            'Nicht gespeicherte Workout-Änderungen gehen verloren.',
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

  static double? _double(String value) =>
      double.tryParse(value.replaceAll(',', '.'));

  static String _number(num value) => value == value.roundToDouble()
      ? value.toInt().toString()
      : value.toStringAsFixed(1);
}

const _notSet = Object();
