import 'package:flutter/material.dart';

import '../features/account/account_controller.dart';
import '../features/catalog/records.dart';
import '../features/profile/profile_editor_controller.dart';
import 'zones_panel.dart';

class ProfileEditorPage extends StatefulWidget {
  const ProfileEditorPage({
    super.key,
    required this.account,
    required this.profile,
  });

  final AccountController account;
  final ProfileRecord profile;

  @override
  State<ProfileEditorPage> createState() => _ProfileEditorPageState();
}

class _ProfileEditorPageState extends State<ProfileEditorPage> {
  late final ProfileEditorController editor = ProfileEditorController(
    widget.account,
    widget.profile,
  );
  late final name = TextEditingController(text: widget.profile.name);
  late final ftp = TextEditingController(text: widget.profile.ftp?.toString());
  late final weight = TextEditingController(
    text: _number(widget.profile.weightKg),
  );
  late final maxHr = TextEditingController(
    text: widget.profile.maxHr?.toString(),
  );
  String? status;

  @override
  void dispose() {
    name.dispose();
    ftp.dispose();
    weight.dispose();
    maxHr.dispose();
    editor.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Profil und Zonen')),
    body: AnimatedBuilder(
      animation: editor,
      builder: (context, _) => ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text(
            'Trainingsprofil',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const Text(
            'Diese Werte steuern deine persönlichen Zielwatt und Zonen.',
          ),
          const SizedBox(height: 20),
          LayoutBuilder(
            builder: (context, constraints) {
              final width = constraints.maxWidth >= 720
                  ? (constraints.maxWidth - 16) / 2
                  : constraints.maxWidth;
              return Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  _Field(
                    fieldKey: const Key('profileName'),
                    width: width,
                    controller: name,
                    label: 'Name',
                    textInputAction: TextInputAction.next,
                  ),
                  _Field(
                    fieldKey: const Key('profileFtp'),
                    width: width,
                    controller: ftp,
                    label: 'FTP (W)',
                    keyboardType: TextInputType.number,
                    textInputAction: TextInputAction.next,
                  ),
                  _Field(
                    fieldKey: const Key('profileWeight'),
                    width: width,
                    controller: weight,
                    label: 'Gewicht (kg, optional)',
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    textInputAction: TextInputAction.next,
                  ),
                  _Field(
                    fieldKey: const Key('profileMaxHr'),
                    width: width,
                    controller: maxHr,
                    label: 'Maximalpuls (bpm, optional)',
                    keyboardType: TextInputType.number,
                    textInputAction: TextInputAction.done,
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 8,
            children: [
              FilledButton(
                key: const Key('saveProfile'),
                onPressed: editor.busy ? null : _save,
                child: const Text('Profil speichern'),
              ),
              TextButton(
                onPressed: editor.busy ? null : () => Navigator.pop(context),
                child: const Text('Abbrechen'),
              ),
            ],
          ),
          if (editor.busy) const LinearProgressIndicator(),
          if (editor.error != null)
            Text(
              editor.error!,
              key: const Key('profileError'),
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (status != null) Text(status!, key: const Key('profileStatus')),
          const SizedBox(height: 28),
          ZonesPanel(
            ftpWatts: editor.profile.ftp,
            maxHeartRate: editor.profile.maxHr,
          ),
        ],
      ),
    ),
  );

  Future<void> _save() async {
    setState(() => status = null);
    final success = await editor.save(
      name: name.text,
      ftp: ftp.text,
      weightKg: weight.text,
      maxHeartRate: maxHr.text,
    );
    if (!mounted || !success) return;
    name.text = editor.profile.name;
    ftp.text = editor.profile.ftp?.toString() ?? '';
    weight.text = _number(editor.profile.weightKg);
    maxHr.text = editor.profile.maxHr?.toString() ?? '';
    setState(() => status = 'Profil wurde vom Server gespeichert.');
  }

  static String _number(num? value) {
    if (value == null) return '';
    return value == value.roundToDouble()
        ? value.toInt().toString()
        : value.toString();
  }
}

class _Field extends StatelessWidget {
  const _Field({
    required this.fieldKey,
    required this.width,
    required this.controller,
    required this.label,
    required this.textInputAction,
    this.keyboardType,
  });

  final Key fieldKey;
  final double width;
  final TextEditingController controller;
  final String label;
  final TextInputType? keyboardType;
  final TextInputAction textInputAction;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: width,
    child: TextField(
      key: fieldKey,
      controller: controller,
      keyboardType: keyboardType,
      textInputAction: textInputAction,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
    ),
  );
}
