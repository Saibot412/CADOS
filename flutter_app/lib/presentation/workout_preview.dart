import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../features/workout/workout.dart';

class WorkoutPreview extends StatelessWidget {
  const WorkoutPreview({super.key, required this.workout});

  final Workout? workout;

  @override
  Widget build(BuildContext context) {
    if (workout == null) {
      return const SizedBox(
        height: 180,
        child: Center(
          child: Text('Vorschau erscheint nach gültigen Blockangaben.'),
        ),
      );
    }
    return Semantics(
      label:
          'Leistungsverlauf mit ${workout!.blocks.length} Blöcken und ${workout!.duration} Sekunden',
      image: true,
      child: SizedBox(
        height: 220,
        width: double.infinity,
        child: CustomPaint(
          painter: _WorkoutPainter(workout!, Theme.of(context).colorScheme),
        ),
      ),
    );
  }
}

class _WorkoutPainter extends CustomPainter {
  const _WorkoutPainter(this.workout, this.colors);

  final Workout workout;
  final ColorScheme colors;

  @override
  void paint(Canvas canvas, Size size) {
    const padding = 18.0;
    final chart = Rect.fromLTRB(
      padding,
      padding,
      size.width - padding,
      size.height - padding,
    );
    final maximum = math.max(
      1,
      workout.blocks.fold<int>(
        0,
        (value, block) => math.max(value, math.max(block.start, block.end)),
      ),
    );
    final background = Paint()..color = colors.surfaceContainerHighest;
    canvas.drawRRect(
      RRect.fromRectAndRadius(chart, const Radius.circular(12)),
      background,
    );
    final line = Paint()
      ..color = colors.primary
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeJoin = StrokeJoin.round;
    final fill = Paint()
      ..color = colors.primary.withValues(alpha: .18)
      ..style = PaintingStyle.fill;
    final path = Path();
    var elapsed = 0;
    double x(int seconds) =>
        chart.left + seconds / workout.duration * chart.width;
    double y(int watts) => chart.bottom - watts / maximum * chart.height * .92;
    path.moveTo(chart.left, chart.bottom);
    for (final block in workout.blocks) {
      path.lineTo(x(elapsed), y(block.start));
      elapsed += block.duration;
      path.lineTo(x(elapsed), y(block.end));
    }
    final linePath = Path.from(path);
    path
      ..lineTo(chart.right, chart.bottom)
      ..close();
    canvas.drawPath(path, fill);
    canvas.drawPath(linePath, line);
  }

  @override
  bool shouldRepaint(covariant _WorkoutPainter oldDelegate) =>
      oldDelegate.workout != workout || oldDelegate.colors != colors;
}
