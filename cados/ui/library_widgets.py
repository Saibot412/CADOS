from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QFrame, QStyle, QStyledItemDelegate, QStyleOptionViewItem

WORKOUT_ITEM_COUNT_ROLE = Qt.UserRole + 1
WORKOUT_ITEM_HEADER_ROLE = Qt.UserRole + 2


def format_duration(seconds: int) -> str:
    hours, remainder = divmod(max(0, int(seconds)), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_timestamp(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


class _NoScrollComboBox(QComboBox):
    """ComboBox that sizes its popup to fit all items without a scrollbar."""

    def showPopup(self) -> None:  # noqa: N802
        view = self.view()
        model = self.model()
        if model is not None and model.rowCount() > 0:
            total = sum(view.sizeHintForRow(i) for i in range(model.rowCount()))
            total += 2 * view.frameWidth() + 10
            view.setMinimumHeight(total)
        super().showPopup()
        # Force white background on the popup container and all its children
        popup = self.findChild(QFrame)
        if popup is not None:
            popup.setStyleSheet("background: #ffffff;")
        container = view.parent()
        if container is not None:
            container.setStyleSheet(
                "background: #ffffff; border: 1px solid #d8dee6; border-radius: 8px;"
            )


class _WorkoutListDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.state &= ~QStyle.State_HasFocus
        if bool(index.data(WORKOUT_ITEM_HEADER_ROLE)):
            painter.save()
            header_rect = option.rect.adjusted(10, 8, -10, -2)
            font = QFont(option.font)
            font.setPointSize(max(9, font.pointSize() - 1))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(QColor("#7a90a7")))
            painter.drawText(header_rect, Qt.AlignLeft | Qt.AlignVCenter, str(index.data(Qt.DisplayRole) or "").upper())
            painter.restore()
            return

        painter.save()

        text = index.data(Qt.DisplayRole) or ""
        count = index.data(WORKOUT_ITEM_COUNT_ROLE) or "0x"
        row_rect = opt.rect.adjusted(4, 1, -4, -1)
        content_rect = row_rect.adjusted(12, 4, -12, -4)

        badge_font = QFont(opt.font)
        badge_font.setPointSize(max(9, badge_font.pointSize() - 1))
        badge_font.setBold(True)
        painter.setFont(badge_font)
        badge_metrics = painter.fontMetrics()
        badge_width = max(38, badge_metrics.horizontalAdvance(str(count)) + 16)
        badge_rect = QRect(
            content_rect.right() - badge_width,
            content_rect.top() + max(0, (content_rect.height() - 24) // 2),
            badge_width,
            24,
        )

        is_selected = bool(opt.state & QStyle.State_Selected)
        is_hovered = bool(opt.state & QStyle.State_MouseOver)

        if is_selected:
            painter.setPen(QPen(QColor("#c9d9ec"), 1))
            painter.setBrush(QColor("#deebff"))
            painter.drawRoundedRect(row_rect, 12, 12)
            text_color = QColor("#10233a")
            badge_fill = QColor("#ffffff")
            badge_border = QColor("#bfd3eb")
            badge_text = QColor("#5a7088")
        elif is_hovered:
            painter.setPen(QPen(QColor("#dce6f1"), 1))
            painter.setBrush(QColor("#eef5ff"))
            painter.drawRoundedRect(row_rect, 12, 12)
            text_color = QColor("#142033")
            badge_fill = QColor("#ffffff")
            badge_border = QColor("#d6e1eb")
            badge_text = QColor("#6d7a8b")
        else:
            if index.row() % 2:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(246, 248, 251, 180))
                painter.drawRoundedRect(row_rect, 12, 12)
            text_color = QColor("#142033")
            badge_fill = QColor("#eff3f7")
            badge_border = QColor("#dde6ee")
            badge_text = QColor("#6d7a8b")

        text_rect = content_rect
        text_rect.setRight(badge_rect.left() - 10)

        painter.setPen(QPen(text_color))
        painter.setFont(opt.font)
        elided_text = painter.fontMetrics().elidedText(str(text), Qt.ElideRight, max(20, text_rect.width()))
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided_text)

        painter.setPen(QPen(badge_border, 1))
        painter.setBrush(badge_fill)
        painter.drawRoundedRect(badge_rect, 11, 11)

        painter.setPen(QPen(badge_text))
        painter.setFont(badge_font)
        painter.drawText(badge_rect, Qt.AlignCenter, str(count))
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        if bool(index.data(WORKOUT_ITEM_HEADER_ROLE)):
            return QSize(super().sizeHint(option, index).width(), 26)
        base = super().sizeHint(option, index)
        return QSize(base.width(), max(34, base.height() + 8))
