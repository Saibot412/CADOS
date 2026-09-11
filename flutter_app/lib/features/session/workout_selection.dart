part of 'workout_session_controller.dart';

/// Catalog/profile selection is distinct from the running device coordinator.
extension WorkoutSelection on WorkoutSessionController {
  ProfileRecord get _profile {
    final profiles = account.catalog?.profiles;
    if (profiles == null ||
        profiles.length != 1 ||
        profiles.single.ftp == null ||
        profiles.single.ftp! < 30 ||
        profiles.single.ftp! > 2000) {
      throw const FormatException(
        'Genau ein gültiges Profil mit FTP ist erforderlich. Bitte Konto synchronisieren.',
      );
    }
    return profiles.single;
  }

  String? get readiness {
    if (_completionPending && hasSession) {
      return 'Workout ist zu Ende. Bitte Beenden / Speichern erneut versuchen.';
    }
    if (!initialized) return 'Trainingsspeicher wird geprüft.';
    if (recovery != null) {
      return 'Zuerst die unterbrochene Einheit wiederherstellen oder verwerfen.';
    }
    if (account.user == null ||
        !account.user!.active ||
        account.catalog == null) {
      return 'Bitte anmelden und Kontodaten synchronisieren.';
    }
    if (selected == null && data == null) {
      return 'Bitte ein Workout aus deiner Bibliothek auswählen.';
    }
    try {
      _profile;
    } on FormatException catch (e) {
      return e.message;
    }
    if (!trainer.connected) {
      return 'Trainer nicht verbunden. Bitte in Einstellungen verbinden.';
    }
    if (trainer.busy) return 'Trainer ist noch beschäftigt.';
    if (data != null &&
        (data!.accountId != account.user!.id ||
            data!.server != account.config.base.toString())) {
      return 'Bitte mit dem ursprünglichen Konto und Server anmelden.';
    }
    return null;
  }

  void select(WorkoutRecord workout, {String? plan}) {
    if (!canSelect) {
      error = 'Bitte die laufende oder gesicherte Einheit zuerst beenden.';
      _changed();
      return;
    }
    try {
      final current = account.catalog?.workouts
          .where((w) => w.record.id == workout.record.id)
          .toList();
      if (account.user == null || current == null || current.length != 1) {
        throw const FormatException(
          'Workout ist nicht im aktuellen Konto verfügbar.',
        );
      }
      WorkoutParser.validate(current.single.record.payload);
      if (plan != null &&
          !account.catalog!
              .upcoming(clock.now().toLocal())
              .any(
                (p) => p.record.id == plan && p.workoutId == workout.record.id,
              )) {
        throw const FormatException(
          'Geplante Einheit ist nicht mehr verfügbar.',
        );
      }
      selected = current.single;
      planId = plan;
      engine = null;
      error = null;
    } on FormatException catch (e) {
      error = e.message;
    }
    _changed();
  }
}
