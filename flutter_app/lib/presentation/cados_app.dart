import 'dart:async';

import 'package:flutter/material.dart';

import '../features/account/account_controller.dart';
import '../features/trainer/trainer_controller.dart';
import '../features/heart_rate/heart_rate_controller.dart';
import 'account_settings.dart';
import 'catalog_pages.dart';
import 'diagnostics_panel.dart';
import 'training_screen.dart';
import 'device_settings.dart';
import '../features/session/workout_session_controller.dart';
import '../features/session/session_sync_controller.dart';

class CadosApp extends StatefulWidget {
  const CadosApp({
    super.key,
    required this.account,
    required this.controller,
    required this.session,
    required this.sync,
    this.heartRate,
    this.exportLog,
    this.closeHttp,
  });
  final WorkoutSessionController session;
  final SessionSyncController sync;
  final AccountController account;
  final TrainerController controller;
  final HeartRateController? heartRate;
  final Future<void> Function()? exportLog;
  final void Function()? closeHttp;
  @override
  State<CadosApp> createState() => _CadosAppState();
}

class _CadosAppState extends State<CadosApp> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      unawaited(widget.session.background());
    }
  }

  int selected = 0;
  static const labels = ['Heute', 'Workouts', 'Training', 'Einstellungen'];
  static const icons = [
    Icons.today,
    Icons.library_books,
    Icons.directions_bike,
    Icons.settings,
  ];
  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_closeDevices());
    super.dispose();
  }

  Future<void> _closeDevices() async {
    try {
      await widget.session.shutdown();
      widget.session.dispose();
      widget.sync.dispose();
      await widget.sync.closed;
      widget.account.dispose();
      widget.closeHttp?.call();
      widget.controller.dispose();
      widget.heartRate?.dispose();
      await Future.wait([
        widget.controller.closed,
        if (widget.heartRate != null) widget.heartRate!.closed,
      ]);
    } finally {
      await widget.controller.logger?.close();
    }
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'CADOS',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xff00866b),
        brightness: Brightness.dark,
      ),
    ),
    home: AnimatedBuilder(
      animation: Listenable.merge([widget.account, widget.session]),
      builder: (context, _) {
        final a = widget.account;
        final pages = [
          CatalogPage(
            account: a,
            workouts: false,
            onSelect: (workout, plan) {
              widget.session.select(workout, plan: plan);
              setState(() => selected = 2);
            },
          ),
          CatalogPage(
            account: a,
            workouts: true,
            onSelect: (workout, plan) {
              widget.session.select(workout, plan: plan);
              setState(() => selected = 2);
            },
          ),
          TrainingScreen(session: widget.session, sync: widget.sync),
          AccountSettings(
            account: a,
            devices: DeviceSettings(
              trainer: widget.controller,
              heartRate: widget.heartRate,
              locked: widget.session.hasSession,
            ),
            support: AnimatedBuilder(
              animation: widget.controller,
              builder: (context, _) => Column(
                children: [
                  Text(
                    'Trainer: ${connectionLabel(widget.controller.connection.phase)}',
                  ),
                  if (widget.heartRate != null)
                    AnimatedBuilder(
                      animation: widget.heartRate!,
                      builder: (context, _) => Text(
                        'Herzfrequenz: ${connectionLabel(widget.heartRate!.connection.phase)}',
                      ),
                    ),
                  DiagnosticsPanel(
                    logger: widget.controller.logger,
                    fallback: widget.controller.logs,
                    exportLog: widget.exportLog,
                  ),
                ],
              ),
            ),
          ),
        ];
        return LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth >= 760;
            return Scaffold(
              appBar: AppBar(
                title: Text('CADOS · ${labels[selected]}'),
                actions: [
                  IconButton(
                    tooltip: 'Kontodaten aktualisieren',
                    onPressed: a.busy ? null : a.refresh,
                    icon: const Icon(Icons.refresh),
                  ),
                ],
              ),
              body: Column(
                children: [
                  if (a.busy) const LinearProgressIndicator(),
                  if (a.error != null)
                    MaterialBanner(
                      content: Text(a.error!),
                      actions: [
                        TextButton(
                          onPressed: a.busy ? null : a.refresh,
                          child: const Text('Erneut versuchen'),
                        ),
                      ],
                    ),
                  Expanded(
                    child: Row(
                      children: [
                        if (wide)
                          NavigationRail(
                            selectedIndex: selected,
                            labelType: NavigationRailLabelType.all,
                            onDestinationSelected: (i) =>
                                setState(() => selected = i),
                            destinations: [
                              for (var i = 0; i < labels.length; i++)
                                NavigationRailDestination(
                                  icon: Icon(icons[i]),
                                  label: Text(labels[i]),
                                ),
                            ],
                          ),
                        Expanded(
                          child: IndexedStack(index: selected, children: pages),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              bottomNavigationBar: wide
                  ? null
                  : NavigationBar(
                      selectedIndex: selected,
                      onDestinationSelected: (i) =>
                          setState(() => selected = i),
                      destinations: [
                        for (var i = 0; i < labels.length; i++)
                          NavigationDestination(
                            icon: Icon(icons[i]),
                            label: labels[i],
                          ),
                      ],
                    ),
            );
          },
        );
      },
    ),
  );
}
