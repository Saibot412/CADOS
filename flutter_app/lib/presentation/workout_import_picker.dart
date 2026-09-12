import 'package:file_selector/file_selector.dart';

import '../features/workout/workout_import.dart';

const _workoutTypes = XTypeGroup(
  label: 'CADOS Workouts',
  extensions: ['json', 'zwo'],
);

Future<WorkoutImportSource?> pickWorkoutImportSource() async {
  final file = await openFile(acceptedTypeGroups: const [_workoutTypes]);
  if (file == null) return null;
  final length = await file.length();
  if (length <= 0 || length > 2000000) {
    throw const FormatException(
      'Die Importdatei muss zwischen 1 Byte und 2 MB groß sein.',
    );
  }
  return WorkoutImportSource(file.name, await file.readAsString());
}
