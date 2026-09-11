/// Python round(): ties go to the even integer, unlike Dart round().
int pythonRound(double value) {
  final lower = value.floor();
  if (value - lower == 0.5) return lower.isEven ? lower : lower + 1;
  return value.round();
}

enum BlockKind { steady, ramp }

class WorkoutBlock {
  const WorkoutBlock({
    required this.kind,
    required this.label,
    required this.duration,
    this.targetWatts,
    this.targetPct,
    this.startWatts,
    this.endWatts,
    this.startPct,
    this.endPct,
    this.cadence,
  });
  final BlockKind kind;
  final String label;
  final int duration;
  final int? targetWatts, startWatts, endWatts, cadence;
  final double? targetPct, startPct, endPct;
  ResolvedBlock resolve(int ftp) {
    int power(double? pct, int? watts) {
      if (pct != null) {
        if (!pct.isFinite) throw ArgumentError('Non-finite FTP fraction');
        final resolved = pythonRound(ftp * pct);
        return resolved < 1 ? 1 : resolved;
      }
      if (watts == null) throw ArgumentError('Unresolved block $label');
      return watts;
    }

    if (duration <= 0) throw ArgumentError('Block duration must be positive');
    final start = kind == BlockKind.steady
        ? power(targetPct, targetWatts)
        : power(startPct, startWatts);
    return ResolvedBlock(
      label,
      duration,
      start,
      kind == BlockKind.steady ? start : power(endPct, endWatts),
      cadence,
    );
  }
}

class ResolvedBlock {
  const ResolvedBlock(
    this.label,
    this.duration,
    this.start,
    this.end,
    this.cadence,
  );
  final String label;
  final int duration, start, end;
  final int? cadence;
  int targetAt(double seconds) {
    // Reference uses `end_watts or start`: preserve its zero-end fallback.
    final effectiveEnd = end == 0 ? start : end;
    return pythonRound(
      start + (effectiveEnd - start) * (seconds / duration).clamp(0, 1),
    );
  }
}

class Workout {
  Workout(this.name, List<WorkoutBlock> blocks, {int? ftp, int? ftpReference}) {
    final candidate = (ftp == null || ftp == 0)
        ? (ftpReference == null || ftpReference == 0 ? 200 : ftpReference)
        : ftp;
    ftpWatts = candidate <= 0 ? 200 : candidate;
    if (blocks.isEmpty) throw ArgumentError('Workout contains no blocks');
    this.blocks = List.unmodifiable(blocks.map((b) => b.resolve(ftpWatts)));
  }
  final String name;
  late final int ftpWatts;
  late final List<ResolvedBlock> blocks;
  int get duration => blocks.fold(0, (sum, b) => sum + b.duration);
  (int, ResolvedBlock, double) locate(double elapsed) {
    var remaining = elapsed.clamp(0.0, duration - 0.000001);
    for (var i = 0; i < blocks.length; i++) {
      if (remaining < blocks[i].duration || i == blocks.length - 1) {
        return (i, blocks[i], remaining);
      }
      remaining -= blocks[i].duration;
    }
    throw StateError('Empty workout');
  }
}
