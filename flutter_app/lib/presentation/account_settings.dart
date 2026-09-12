import 'package:flutter/material.dart';

import '../features/account/account_controller.dart';
import 'profile_editor.dart';

class AccountSettings extends StatefulWidget {
  const AccountSettings({
    super.key,
    required this.account,
    required this.devices,
    required this.support,
  });
  final AccountController account;
  final Widget support, devices;
  @override
  State<AccountSettings> createState() => _AccountSettingsState();
}

class _AccountSettingsState extends State<AccountSettings> {
  final email = TextEditingController(), password = TextEditingController();
  late final server = TextEditingController(
    text: widget.account.config.base.toString(),
  );
  late String displayedOrigin = widget.account.config.base.toString();
  @override
  void didUpdateWidget(covariant AccountSettings oldWidget) {
    super.didUpdateWidget(oldWidget);
    final origin = widget.account.config.base.toString();
    if (displayedOrigin != origin) {
      server.text = origin;
      displayedOrigin = origin;
    }
  }

  @override
  void dispose() {
    email.dispose();
    password.dispose();
    server.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final a = widget.account;
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text('Konto', style: Theme.of(context).textTheme.headlineSmall),
        if (a.user != null) ...[
          Text(a.user!.email),
          for (final profile in a.catalog?.profiles ?? [])
            Card(
              child: ListTile(
                title: Text(profile.name),
                subtitle: Text(
                  'FTP ${profile.ftp ?? '–'} W · Gewicht ${profile.weightKg ?? '–'} kg · HFmax ${profile.maxHr ?? '–'} bpm',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: a.busy
                    ? null
                    : () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) =>
                              ProfileEditorPage(account: a, profile: profile),
                        ),
                      ),
              ),
            ),
          if (a.catalog != null && a.catalog!.profiles.isEmpty)
            const Text('Kein Trainingsprofil im Konto vorhanden.'),
          OutlinedButton(
            onPressed: a.busy ? null : a.logout,
            child: const Text('Abmelden'),
          ),
        ] else ...[
          const Text(
            'Anmelden, um dein CADOS-Profil, Workouts und Kalender zu laden.',
          ),
          TextField(
            controller: email,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(labelText: 'E-Mail'),
          ),
          TextField(
            controller: password,
            obscureText: true,
            autocorrect: false,
            enableSuggestions: false,
            decoration: const InputDecoration(labelText: 'Passwort'),
          ),
          FilledButton(
            onPressed: a.busy
                ? null
                : () async {
                    final credential = password.text;
                    password.clear();
                    await a.login(email.text, credential);
                  },
            child: const Text('Anmelden'),
          ),
          TextButton(
            onPressed: a.busy ? null : a.restore,
            child: const Text('Gespeicherte Anmeldung erneut versuchen'),
          ),
        ],
        const SizedBox(height: 24),
        TextField(
          controller: server,
          decoration: const InputDecoration(
            labelText: 'CADOS-Server',
            helperText: 'HTTPS-Serveradresse. Ein Serverwechsel meldet diese Ansicht ab.',
          ),
        ),
        OutlinedButton(
          onPressed: a.busy ? null : () => a.changeServer(server.text),
          child: const Text('Server speichern'),
        ),
        const SizedBox(height: 24),
        widget.devices,
        const SizedBox(height: 24),
        ExpansionTile(
          title: const Text('Diagnostik & Support'),
          children: [widget.support],
        ),
      ],
    );
  }
}
