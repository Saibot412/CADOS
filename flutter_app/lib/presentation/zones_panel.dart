import 'package:flutter/material.dart';

import '../features/profile/training_zones.dart';

class ZonesPanel extends StatelessWidget {
  const ZonesPanel({super.key, required this.ftpWatts, this.maxHeartRate});

  final int? ftpWatts;
  final int? maxHeartRate;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final wide = constraints.maxWidth >= 760;
      final sectionWidth = wide
          ? (constraints.maxWidth - 16) / 2
          : constraints.maxWidth;
      return Wrap(
        spacing: 16,
        runSpacing: 16,
        children: [
          SizedBox(
            width: sectionWidth,
            child: _ZoneSection(
              title: 'Leistungszonen',
              anchor: ftpWatts == null ? null : 'FTP $ftpWatts W',
              missing: 'Ohne FTP können keine Leistungszonen berechnet werden.',
              zones: ftpWatts == null ? const [] : powerZones(ftpWatts!),
            ),
          ),
          SizedBox(
            width: sectionWidth,
            child: _ZoneSection(
              title: 'Herzfrequenzzonen',
              anchor: maxHeartRate == null ? null : 'HFmax $maxHeartRate bpm',
              missing: 'Maximalpuls fehlt. Herzfrequenzzonen werden erst nach dem Eintragen angezeigt.',
              zones: maxHeartRate == null
                  ? const []
                  : heartRateZones(maxHeartRate!),
            ),
          ),
        ],
      );
    },
  );
}

class _ZoneSection extends StatelessWidget {
  const _ZoneSection({
    required this.title,
    required this.anchor,
    required this.missing,
    required this.zones,
  });

  final String title, missing;
  final String? anchor;
  final List<TrainingZone> zones;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          if (anchor != null) Text(anchor!),
          const SizedBox(height: 12),
          if (zones.isEmpty)
            Text(missing)
          else
            for (final zone in zones)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Row(
                  children: [
                    Container(
                      width: 10,
                      height: 34,
                      decoration: BoxDecoration(
                        color: _color(zone.colorHex),
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            zone.label,
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          Text(zone.percentLabel),
                        ],
                      ),
                    ),
                    Text(zone.rangeLabel),
                  ],
                ),
              ),
        ],
      ),
    ),
  );

  Color _color(String hex) =>
      Color(int.parse(hex.substring(1), radix: 16) | 0xff000000);
}
