from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from cados.core.zones import POWER_ZONES, power_zone_bounds_watts, split_block_into_zone_segments
from cados.models.workout import ResolvedWorkout


def _format_duration(seconds: int) -> str:
    minutes, secs = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class WorkoutTimelineWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._workout: ResolvedWorkout | None = None
        self._ftp = 250
        self._active_block_index = -1
        self._elapsed_sec = 0
        self._variant = "preview"
        self.setMinimumHeight(128)

    def set_workout(self, workout: ResolvedWorkout | None, ftp: int | None = None) -> None:
        self._workout = workout
        if ftp is not None:
            self._ftp = ftp
        self.update()

    def set_variant(self, variant: str) -> None:
        self._variant = "focus" if variant == "focus" else "preview"
        self.update()

    def set_state(self, active_block_index: int, elapsed_sec: int) -> None:
        self._active_block_index = active_block_index
        self._elapsed_sec = elapsed_sec
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        surface_rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        surface_top, surface_bottom, border_color = self._surface_colors()
        surface_gradient = QLinearGradient(surface_rect.topLeft(), surface_rect.bottomLeft())
        surface_gradient.setColorAt(0.0, surface_top)
        surface_gradient.setColorAt(1.0, surface_bottom)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(surface_gradient)
        painter.drawRoundedRect(surface_rect, 18, 18)

        if self._workout is None or not self._workout.blocks:
            painter.setPen(self._muted_text())
            painter.drawText(surface_rect.toRect(), Qt.AlignCenter, "Keine Timeline verfügbar")
            return

        chart_rect = surface_rect.adjusted(48, 40, -64, -34)
        if chart_rect.width() <= 0 or chart_rect.height() <= 0:
            return

        total_duration = max(1, self._workout.total_duration_sec)
        min_watts, max_watts = self._watt_bounds()
        cadence_bounds = self._cadence_bounds()
        metrics = QFontMetrics(self.font())

        self._draw_top_axis_labels(painter, chart_rect, total_duration, metrics)
        self._draw_zone_bands(painter, chart_rect, min_watts, max_watts, metrics)
        self._draw_grid(painter, chart_rect, min_watts, max_watts, cadence_bounds)
        self._draw_block_highlight(painter, chart_rect, total_duration)
        self._draw_profile(painter, chart_rect, total_duration, min_watts, max_watts)
        if cadence_bounds is not None:
            self._draw_cadence_profile(painter, chart_rect, total_duration, cadence_bounds)

        progress = min(max(self._elapsed_sec / total_duration, 0.0), 1.0)
        progress_x = chart_rect.left() + chart_rect.width() * progress
        current_target = self._current_target_watts()
        current_y = self._watts_to_y(current_target, chart_rect, min_watts, max_watts)
        accent = self._accent_color()

        progress_pen = QPen(accent, 3 if self._variant == "focus" else 2)
        progress_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(progress_pen)
        painter.drawLine(progress_x, chart_rect.top() - 4, progress_x, chart_rect.bottom() + 4)
        painter.setPen(QPen(self._surface_base_color(), 2))
        painter.setBrush(accent)
        painter.drawEllipse(QPointF(progress_x, current_y), 5.5, 5.5)
        if cadence_bounds is not None:
            current_cadence = self._current_target_cadence()
            if current_cadence is not None:
                cadence_y = self._cadence_to_y(current_cadence, chart_rect, cadence_bounds[0], cadence_bounds[1])
                cadence_color = self._cadence_color()
                painter.setPen(QPen(self._surface_base_color(), 2))
                painter.setBrush(cadence_color)
                painter.drawEllipse(QPointF(progress_x, cadence_y), 4.0, 4.0)

        painter.setPen(self._muted_text())
        painter.drawText(QRectF(chart_rect.left(), chart_rect.bottom() + 8, 100, 18), Qt.AlignLeft, "0:00")
        total_label = _format_duration(total_duration)
        total_width = metrics.horizontalAdvance(total_label)
        painter.drawText(
            QRectF(chart_rect.right() - total_width, chart_rect.bottom() + 8, total_width + 2, 18),
            Qt.AlignRight,
            total_label,
        )

    def _draw_top_axis_labels(self, painter: QPainter, chart_rect: QRectF, total_duration: int, metrics: QFontMetrics) -> None:
        axis_y = chart_rect.top() - 12
        painter.setPen(QPen(self._grid_color(), 1))
        painter.drawLine(chart_rect.left(), axis_y, chart_rect.right(), axis_y)

        cursor = 0
        painter.setPen(self._muted_text())
        for block in self._workout.blocks:
            start_x = self._time_to_x(cursor, chart_rect, total_duration)
            end_x = self._time_to_x(cursor + block.duration_sec, chart_rect, total_duration)
            width = end_x - start_x

            painter.setPen(QPen(self._grid_color(), 1))
            painter.drawLine(start_x, axis_y - 4, start_x, axis_y + 4)
            painter.setPen(self._muted_text())

            label = self._block_duration_label(block.duration_sec, width, metrics)
            if label is not None:
                label_rect = QRectF(start_x + 2, chart_rect.top() - 36, max(0.0, width - 4), 18)
                painter.drawText(label_rect, Qt.AlignCenter, label)
            cursor += block.duration_sec

        end_x = self._time_to_x(total_duration, chart_rect, total_duration)
        painter.setPen(QPen(self._grid_color(), 1))
        painter.drawLine(end_x, axis_y - 4, end_x, axis_y + 4)

    def _draw_grid(
        self,
        painter: QPainter,
        rect: QRectF,
        min_watts: int,
        max_watts: int,
        cadence_bounds: tuple[int, int] | None,
    ) -> None:
        grid_pen = QPen(self._grid_color(), 1)
        painter.setPen(grid_pen)

        for ratio in (0.0, 0.5, 1.0):
            y = rect.bottom() - ratio * rect.height()
            painter.drawLine(rect.left(), y, rect.right(), y)
            watts = round(min_watts + ratio * (max_watts - min_watts))
            painter.setPen(self._muted_text())
            painter.drawText(QRectF(0, y - 10, rect.left() - 8, 20), Qt.AlignRight | Qt.AlignVCenter, f"{watts} W")
            if cadence_bounds is not None:
                cadence = round(cadence_bounds[0] + ratio * (cadence_bounds[1] - cadence_bounds[0]))
                painter.setPen(self._cadence_color())
                painter.drawText(
                    QRectF(rect.right() + 8, y - 10, 52, 20),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    f"{cadence} rpm",
                )
            painter.setPen(grid_pen)

        cursor = 0
        for block in self._workout.blocks[:-1]:
            cursor += block.duration_sec
            x = self._time_to_x(cursor, rect, self._workout.total_duration_sec)
            painter.drawLine(x, rect.top(), x, rect.bottom())

    def _draw_zone_bands(
        self,
        painter: QPainter,
        rect: QRectF,
        min_watts: int,
        max_watts: int,
        metrics: QFontMetrics,
    ) -> None:
        for zone in POWER_ZONES:
            lower, upper = power_zone_bounds_watts(zone, self._ftp)
            visible_low = max(lower, min_watts)
            visible_high = min(max_watts, upper if upper is not None else max_watts)
            if visible_high <= visible_low:
                continue

            top_y = self._watts_to_y(visible_high, rect, min_watts, max_watts)
            bottom_y = self._watts_to_y(visible_low, rect, min_watts, max_watts)
            band_rect = QRectF(rect.left(), top_y, rect.width(), max(1.0, bottom_y - top_y))

            fill = QColor(zone.color)
            fill.setAlpha(18)
            painter.fillRect(band_rect, fill)

            if band_rect.height() >= metrics.height() + 4:
                label_color = QColor(zone.color)
                label_color.setAlpha(170)
                painter.setPen(label_color)
                painter.drawText(
                    QRectF(rect.left() + 8, band_rect.top() + 2, 44, band_rect.height() - 4),
                    Qt.AlignLeft | Qt.AlignTop,
                    zone.code,
                )

    def _draw_cadence_profile(
        self,
        painter: QPainter,
        rect: QRectF,
        total_duration: int,
        cadence_bounds: tuple[int, int],
    ) -> None:
        segments: list[tuple[float, float, float, float]] = []
        previous_x: float | None = None
        previous_y: float | None = None
        cursor = 0
        for block in self._workout.blocks:
            if block.target_cadence is None:
                previous_x = None
                previous_y = None
                cursor += block.duration_sec
                continue

            start_x = self._time_to_x(cursor, rect, total_duration)
            end_x = self._time_to_x(cursor + block.duration_sec, rect, total_duration)
            y = self._cadence_to_y(block.target_cadence, rect, cadence_bounds[0], cadence_bounds[1])

            if previous_x is not None and previous_y is not None:
                segments.append((previous_x, previous_y, start_x, y))
            segments.append((start_x, y, end_x, y))

            previous_x = end_x
            previous_y = y
            cursor += block.duration_sec

        if not segments:
            return

        dash_pattern = [7, 4] if self._variant == "focus" else [6, 4]
        line_color = QColor(self._cadence_color())
        line_color.setAlpha(210 if self._variant == "focus" else 185)
        line_pen = QPen(line_color, 2.2 if self._variant == "focus" else 1.8)
        line_pen.setCapStyle(Qt.RoundCap)
        line_pen.setJoinStyle(Qt.RoundJoin)
        line_pen.setStyle(Qt.DashLine)
        line_pen.setDashPattern(dash_pattern)
        painter.setPen(line_pen)
        for x1, y1, x2, y2 in segments:
            painter.drawLine(x1, y1, x2, y2)

    def _draw_block_highlight(self, painter: QPainter, rect: QRectF, total_duration: int) -> None:
        if self._active_block_index < 0 or self._active_block_index >= len(self._workout.blocks):
            return

        start_sec = self._workout.block_start_offset(self._active_block_index)
        end_sec = start_sec + self._workout.blocks[self._active_block_index].duration_sec
        start_x = self._time_to_x(start_sec, rect, total_duration)
        end_x = self._time_to_x(end_sec, rect, total_duration)

        accent = self.palette().highlight().color()
        accent.setAlpha(22)
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(start_x, rect.top(), end_x - start_x, rect.height()), 10, 10)

    def _draw_profile(self, painter: QPainter, rect: QRectF, total_duration: int, min_watts: int, max_watts: int) -> None:
        previous_end_watts: int | None = None
        previous_end_x: float | None = None
        previous_end_y: float | None = None
        cursor = 0

        for block in self._workout.blocks:
            start_sec = cursor
            end_sec = cursor + block.duration_sec
            segments = split_block_into_zone_segments(block, self._ftp)
            for index, segment in enumerate(segments):
                segment_start_sec = start_sec + block.duration_sec * segment.start_progress
                segment_end_sec = start_sec + block.duration_sec * segment.end_progress
                segment_start_x = self._time_to_x(segment_start_sec, rect, total_duration)
                segment_end_x = self._time_to_x(segment_end_sec, rect, total_duration)
                segment_start_y = self._watts_to_y(round(segment.start_watts), rect, min_watts, max_watts)
                segment_end_y = self._watts_to_y(round(segment.end_watts), rect, min_watts, max_watts)

                zone_color = QColor(segment.zone.color)
                zone_fill = QColor(segment.zone.color)
                zone_fill.setAlpha(70 if self._variant == "focus" else 56)

                area_path = QPainterPath(QPointF(segment_start_x, rect.bottom()))
                area_path.lineTo(segment_start_x, segment_start_y)
                area_path.lineTo(segment_end_x, segment_end_y)
                area_path.lineTo(segment_end_x, rect.bottom())
                area_path.closeSubpath()

                line_path = QPainterPath(QPointF(segment_start_x, segment_start_y))
                line_path.lineTo(segment_end_x, segment_end_y)

                if block.kind == "steady":
                    area_path = QPainterPath(QPointF(segment_start_x, rect.bottom()))
                    area_path.lineTo(segment_start_x, segment_start_y)
                    area_path.lineTo(segment_end_x, segment_start_y)
                    area_path.lineTo(segment_end_x, rect.bottom())
                    area_path.closeSubpath()
                    line_path = QPainterPath(QPointF(segment_start_x, segment_start_y))
                    line_path.lineTo(segment_end_x, segment_start_y)
                    segment_end_y = segment_start_y

                painter.setPen(Qt.NoPen)
                painter.setBrush(zone_fill)
                painter.drawPath(area_path)

                if index == 0 and previous_end_watts is not None and previous_end_x is not None and previous_end_y is not None:
                    if previous_end_watts != round(segment.start_watts):
                        connector_pen = QPen(self._step_color(zone_color), 2)
                        painter.setPen(connector_pen)
                        painter.drawLine(previous_end_x, previous_end_y, segment_start_x, segment_start_y)

                line_pen = QPen(zone_color, 3)
                line_pen.setCapStyle(Qt.RoundCap)
                painter.setPen(line_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(line_path)

                previous_end_watts = round(segment.end_watts)
                previous_end_x = segment_end_x
                previous_end_y = segment_end_y

            cursor = end_sec

    def _watt_bounds(self) -> tuple[int, int]:
        watts: list[int] = []
        for block in self._workout.blocks:
            if block.kind == "steady":
                watts.append(int(block.target_watts or 0))
            else:
                watts.append(int(block.start_watts or 0))
                watts.append(int(block.end_watts or 0))

        low = min(watts)
        high = max(watts)
        if low == high:
            low = max(0, low - 20)
            high += 20
        padding = max(15, round((high - low) * 0.12))
        low = max(0, low - padding)
        high = high + padding
        low = (low // 25) * 25
        high = ((high + 24) // 25) * 25
        if high <= low:
            high = low + 25
        return low, high

    def _cadence_bounds(self) -> tuple[int, int] | None:
        cadences = [block.target_cadence for block in self._workout.blocks if block.target_cadence is not None]
        if not cadences:
            return None

        low = min(cadences)
        high = max(cadences)
        if low == high:
            low -= 5
            high += 5
        padding = max(3, round((high - low) * 0.15))
        low = max(40, low - padding)
        high = min(140, high + padding)
        low = (low // 5) * 5
        high = ((high + 4) // 5) * 5
        if high <= low:
            high = low + 5
        return low, high

    def _current_target_watts(self) -> int:
        if self._workout is None or not self._workout.blocks:
            return 0
        _, block, seconds_in_block = self._workout.locate_block(self._elapsed_sec)
        return block.target_watts_at(seconds_in_block)

    def _current_target_cadence(self) -> int | None:
        if self._workout is None or not self._workout.blocks:
            return None
        _, block, _ = self._workout.locate_block(self._elapsed_sec)
        return block.target_cadence

    @staticmethod
    def _block_duration_label(duration_sec: int, width: float, metrics: QFontMetrics) -> str | None:
        full = _format_duration(duration_sec)
        if metrics.horizontalAdvance(full) + 10 <= width:
            return full

        if duration_sec >= 60:
            short = f"{duration_sec // 60}m"
        else:
            short = f"{duration_sec}s"
        if metrics.horizontalAdvance(short) + 10 <= width:
            return short

        return None

    @staticmethod
    def _time_to_x(seconds: float, rect: QRectF, total_duration: int) -> float:
        progress = min(max(seconds / max(1, total_duration), 0.0), 1.0)
        return rect.left() + rect.width() * progress

    @staticmethod
    def _watts_to_y(watts: int, rect: QRectF, min_watts: int, max_watts: int) -> float:
        if max_watts <= min_watts:
            return rect.center().y()
        progress = (watts - min_watts) / (max_watts - min_watts)
        progress = min(max(progress, 0.0), 1.0)
        return rect.bottom() - progress * rect.height()

    @staticmethod
    def _cadence_to_y(cadence: int, rect: QRectF, min_cadence: int, max_cadence: int) -> float:
        if max_cadence <= min_cadence:
            return rect.center().y()
        progress = (cadence - min_cadence) / (max_cadence - min_cadence)
        progress = min(max(progress, 0.0), 1.0)
        return rect.bottom() - progress * rect.height()

    def _muted_text(self) -> QColor:
        return QColor("#5a7088" if self._variant == "focus" else "#7186a0")

    def _grid_color(self) -> QColor:
        color = QColor("#10233a")
        color.setAlpha(30 if self._variant == "focus" else 34)
        return color

    def _cadence_color(self) -> QColor:
        return QColor(self._accent_color())

    def _accent_color(self) -> QColor:
        if self._variant == "focus":
            return QColor("#d43f3a")
        return QColor("#2b84ff")

    def _surface_base_color(self) -> QColor:
        return QColor("#edf2f8" if self._variant == "focus" else "#ffffff")

    def _surface_colors(self) -> tuple[QColor, QColor, QColor]:
        if self._variant == "focus":
            return QColor("#edf2f8"), QColor("#e5ecf4"), QColor("#d0dae8")
        return QColor("#fbfdff"), QColor("#f2f7fb"), QColor("#dce5ef")

    @staticmethod
    def _step_color(base: QColor) -> QColor:
        color = QColor(base)
        color.setAlpha(150)
        return color
