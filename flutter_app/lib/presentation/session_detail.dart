import 'package:flutter/material.dart';

import '../features/account/account_controller.dart';
import '../features/catalog/records.dart';
import '../features/session/ftp_adoption_controller.dart';
import 'training_screen.dart' show trainingTime;

class SessionDetailPage extends StatefulWidget {
  const SessionDetailPage({
    super.key,
    required this.session,
    required this.account,
  });

  final SessionRecord session;
  final AccountController account;

  @override
  State<SessionDetailPage> createState() => _SessionDetailPageState();
}

class _SessionDetailPageState extends State<SessionDetailPage> {
  late final FtpAdoptionController adoption = FtpAdoptionController(
    widget.account,
  );
  bool _keptExistingFtp = false;

  @override
  void dispose() {
    adoption.dispose();
    super.dispose();
  }

  SessionRecord get current {
    final matches = widget.account.catalog?.sessions
        .where((value) => value.record.id == widget.session.record.id)
        .toList();
    return matches?.length == 1 ? matches!.single : widget.session;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Trainingsergebnis')),
    body: AnimatedBuilder(
      animation: Listenable.merge([widget.account, adoption]),
      builder: (context, _) {
        final session = current;
        final payload = session.record.payload;
        final metrics = session.metrics ?? const <String, dynamic>{};
        final ftpResult = session.ftpTestResult;
        return ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Text(
              session.workoutName,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text('${_date(session.timestamp)} · ${_status(session.status)}'),
            if (session.startedAt != null)
              Text(
                'Start: ${_date(session.startedAt!)} · Ende: ${_date(session.timestamp)}',
              ),
            if (payload['plan_id'] is String)
              const Text('Mit einer geplanten Kalendereinheit verknüpft'),
            const SizedBox(height: 24),
            LayoutBuilder(
              builder: (context, constraints) {
                final columns = constraints.maxWidth >= 900
                    ? 4
                    : constraints.maxWidth >= 560
                    ? 2
                    : 1;
                final width =
                    (constraints.maxWidth - (columns - 1) * 12) / columns;
                return Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    _SummaryCard(
                      width: width,
                      label: 'Trainingszeit',
                      value: trainingTime(session.duration),
                    ),
                    _SummaryCard(
                      width: width,
                      label: 'Workoutzeit',
                      value: _seconds(session.workoutElapsedSec),
                    ),
                    _SummaryCard(
                      width: width,
                      label: 'FTP der Einheit',
                      value: _metric(session.ftpWatts, 'W'),
                    ),
                    _SummaryCard(
                      width: width,
                      label: 'Ø Leistung',
                      value: _metric(metrics['avg_watts'], 'W'),
                    ),
                    _SummaryCard(
                      width: width,
                      label: 'Max. Leistung',
                      value: _metric(metrics['max_watts'], 'W'),
                    ),
                    _SummaryCard(
                      width: width,
                      label: 'Normalized Power',
                      value: _metric(metrics['normalized_power'], 'W'),
                    ),
                    _SummaryCard(
                      width: width,
                      label: 'Intensity Factor',
                      value: _number(metrics['intensity_factor'], 2),
                    ),
                    _SummaryCard(
                      width: width,
                      label: 'TSS',
                      value: _number(metrics['tss'], 1),
                    ),
                    _SummaryCard(
                      width: width,
                      label: 'Arbeit',
                      value: _metric(metrics['work_kj'], 'kJ', decimals: 1),
                    ),
                    _SummaryCard(
                      width: width,
                      label: 'Ø Kadenz',
                      value: _metric(metrics['avg_cadence'], 'rpm'),
                    ),
                    _SummaryCard(
                      width: width,
                      label: 'Max. Kadenz',
                      value: _metric(metrics['max_cadence'], 'rpm'),
                    ),
                    _SummaryCard(
                      width: width,
                      label: 'Ø Herzfrequenz',
                      value: _metric(metrics['avg_heart_rate'], 'bpm'),
                    ),
                    _SummaryCard(
                      width: width,
                      label: 'Max. Herzfrequenz',
                      value: _metric(metrics['max_heart_rate'], 'bpm'),
                    ),
                  ],
                );
              },
            ),
            if (ftpResult != null) ...[
              const SizedBox(height: 24),
              _ftpCard(context, session, ftpResult),
            ],
            const SizedBox(height: 24),
            Text(
              session.samples?.isNotEmpty == true
                  ? '${session.samples!.length} echte Messabschnitte gespeichert'
                  : 'Für diese Einheit sind keine Messwerte vorhanden.',
            ),
          ],
        );
      },
    ),
  );

  Widget _ftpCard(
    BuildContext context,
    SessionRecord session,
    Map<String, dynamic> result,
  ) {
    final eligible = result['eligible'] == true;
    final applied = result['applied_at'] != null;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'FTP-Rampentest',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            if (!eligible)
              Text(
                result['reason']?.toString() ??
                    'Für diesen Test ist keine FTP-Schätzung möglich.',
              )
            else ...[
              Text('Bisherige FTP: ${result['old_ftp']} W'),
              Text('Beste gemessene Minute: ${result['best_minute_watts']} W'),
              Text('Ermittelte FTP: ${result['estimated_ftp']} W'),
              const Text(
                'Die Schätzung verwendet ausschließlich gemessene Leistung aus dem Belastungsteil.',
              ),
              const SizedBox(height: 12),
              if (applied)
                const Text('Dieser FTP-Wert wurde bereits übernommen.')
              else if (_keptExistingFtp)
                const Text('Die bisherige FTP bleibt unverändert.')
              else
                Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  children: [
                    FilledButton(
                      key: const Key('adoptFtp'),
                      onPressed: adoption.busy
                          ? null
                          : () => _confirmAdoption(context, session, result),
                      child: Text(
                        '${result['estimated_ftp']} W als neue FTP übernehmen',
                      ),
                    ),
                    TextButton(
                      onPressed: adoption.busy
                          ? null
                          : () => setState(() {
                              _keptExistingFtp = true;
                              adoption.error = null;
                            }),
                      child: const Text('Bisherige FTP behalten'),
                    ),
                  ],
                ),
            ],
            if (adoption.busy) const LinearProgressIndicator(),
            if (adoption.applied)
              const Text(
                'Neue FTP wurde vom Server bestätigt und gespeichert.',
              ),
            if (adoption.error != null)
              Text(
                adoption.error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmAdoption(
    BuildContext context,
    SessionRecord session,
    Map<String, dynamic> result,
  ) async {
    final profiles = widget.account.catalog?.profiles;
    final currentFtp = profiles?.length == 1 ? profiles!.single.ftp : null;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('FTP wirklich übernehmen?'),
        content: Text(
          'Die Profil-FTP wird${currentFtp == null ? '' : ' von $currentFtp W'} auf ${result['estimated_ftp']} W geändert.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('FTP übernehmen'),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) await adoption.adopt(session);
  }

  String _date(DateTime value) {
    final local = value.toLocal();
    return '${local.day.toString().padLeft(2, '0')}.${local.month.toString().padLeft(2, '0')}.${local.year} '
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
  }

  String _status(String status) => switch (status) {
    'completed' => 'Abgeschlossen',
    'stopped' => 'Beendet',
    _ => 'Status unbekannt',
  };

  String _seconds(Object? value) =>
      value is num && value.isFinite && value >= 0 ? trainingTime(value) : '–';

  String _metric(Object? value, String unit, {int decimals = 0}) {
    final number = value is num && value.isFinite ? value : null;
    return number == null ? '–' : '${number.toStringAsFixed(decimals)} $unit';
  }

  String _number(Object? value, int decimals) {
    final number = value is num && value.isFinite ? value : null;
    return number == null ? '–' : number.toStringAsFixed(decimals);
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.width,
    required this.label,
    required this.value,
  });

  final double width;
  final String label, value;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: width,
    child: Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label),
            const SizedBox(height: 4),
            Text(value, style: Theme.of(context).textTheme.headlineSmall),
          ],
        ),
      ),
    ),
  );
}
