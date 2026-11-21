import math
from typing import cast

from PySide6.QtCharts import QChart, QChartView, QLegend, QPieSeries, QPieSlice
from PySide6.QtCore import QMargins, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gogo.ui.graphics.string_to_qcolor import string_to_qcolor

from .constants import CATEGORY_COLORS
from .utils import format_bytes


class ChartWidget(QWidget):
    """A widget for displaying the disk usage pie chart and its controls."""

    category_selected = Signal(str)
    category_hovered = Signal(bool, str, int, int)
    refreshed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._stats: dict | None = None
        self._exploded_slice: QPieSlice | None = None
        self._display_total_size = 0
        self._display_total_count = 0

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._chart_view = self._create_chart_section()
        layout.addWidget(self._chart_view, 1)
        layout.addWidget(self._create_chart_controls())

    def _create_chart_section(self) -> QChartView:
        self._chart = QChart()
        self._chart.setMargins(QMargins(0, 0, 0, 0))
        self._chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self._chart.setBackgroundVisible(False)

        legend = self._chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignLeft)
        legend.setMarkerShape(QLegend.MarkerShape.MarkerShapeCircle)

        view = QChartView(self._chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setStyleSheet("background: transparent;")
        return view

    def _create_chart_controls(self) -> QGroupBox:
        group = QGroupBox("Chart Options")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Scale:"))
        self._scale_selector = QComboBox()
        self._scale_selector.addItems(["Linear", "Logarithmic"])
        self._scale_selector.currentTextChanged.connect(self.refresh)
        layout.addWidget(self._scale_selector)

        layout.addStretch()
        self._git_toggle = QCheckBox("Include .git")
        self._git_toggle.stateChanged.connect(self.refresh)

        self._godot_toggle = QCheckBox("Include .godot")
        self._godot_toggle.setChecked(True)
        self._godot_toggle.stateChanged.connect(self.refresh)

        layout.addWidget(self._git_toggle)
        layout.addWidget(self._godot_toggle)

        return group

    def set_stats(self, stats: dict):
        self._stats = stats
        self.refresh()

    def refresh(self):
        """Rebuild the pie chart from the stats and the current toggles."""
        if not self._stats:
            return

        self._exploded_slice = None
        self._chart.removeAllSeries()

        show_git = self._git_toggle.isChecked()
        show_godot = self._godot_toggle.isChecked()
        use_log = self._scale_selector.currentText() == "Logarithmic"

        series = QPieSeries()
        series.setHoleSize(0.25)

        self._display_total_size = 0
        self._display_total_count = 0

        largest_cat_name = None

        valid_items = [
            (k, v) for k, v in self._stats.items() if k != "Total" and v["count"] > 0
        ]
        sorted_items = sorted(valid_items, key=lambda x: x[1]["size"], reverse=True)

        for label, data in sorted_items:
            if not show_git and label == "Git Data":
                continue
            if not show_godot and label == "Godot Data":
                continue

            if largest_cat_name is None:
                largest_cat_name = label

            self._display_total_size += data["size"]
            self._display_total_count += data["count"]

            if use_log:
                chart_value = math.log10(data["size"] + 1) + 0.5
            else:
                chart_value = data["size"]

            readable_size = format_bytes(data["size"])
            slice_item = series.append(f"{label} ({readable_size})", chart_value)

            color = QColor(CATEGORY_COLORS.get(label, string_to_qcolor(label)))
            slice_item.setBrush(color)

            slice_item.setProperty("category_label", label)
            slice_item.clicked.connect(self._on_slice_clicked)
            slice_item.hovered.connect(
                lambda state, l=label, s=data["size"], c=data["count"]: (
                    self.category_hovered.emit(state, l, s, c)
                )
            )

        self._chart.addSeries(series)
        self._update_legend_colors()

        for marker in self._chart.legend().markers():
            marker.clicked.connect(self._on_marker_clicked)

        if largest_cat_name:
            for slice_item in series.slices():
                if slice_item.property("category_label") == largest_cat_name:
                    QTimer.singleShot(100, slice_item.clicked.emit)
                    break
        self.refreshed.emit()

    def get_display_totals(self) -> tuple[int, int]:
        return self._display_total_size, self._display_total_count

    def get_dominant_category(self) -> tuple[str, int] | None:
        if not self._stats:
            return None

        show_git = self._git_toggle.isChecked()
        show_godot = self._godot_toggle.isChecked()

        largest_size = 0
        largest_name = ""

        for cat, data in self._stats.items():
            if cat == "Total" or data["size"] <= largest_size:
                continue
            if not show_git and cat == "Git Data":
                continue
            if not show_godot and cat == "Godot Data":
                continue
            largest_size = data["size"]
            largest_name = cat

        return (largest_name, largest_size) if largest_name else None

    def _on_marker_clicked(self):
        marker = self.sender()
        if not marker:
            return

        label = marker.label()
        series_list = self._chart.series()
        if not series_list:
            return

        series = series_list[0]
        if isinstance(series, QPieSeries):
            for slice_item in series.slices():
                if slice_item.label() == label:
                    self._on_slice_clicked(slice_item)
                    break

    def _on_slice_clicked(self, slice_item: QPieSlice | None = None) -> None:
        if slice_item is None:
            slice_item = cast(QPieSlice, self.sender())
        if not slice_item:
            return

        if self._exploded_slice and self._exploded_slice == slice_item:
            slice_item.setExploded(False)
            self._exploded_slice = None
            self.category_selected.emit(None)
            return

        if self._exploded_slice:
            self._exploded_slice.setExploded(False)

        slice_item.setExploded(True)
        self._exploded_slice = slice_item

        category = slice_item.property("category_label")
        self.category_selected.emit(category)

    def _update_legend_colors(self):
        if not self._chart.legend().markers():
            return

        text_color = self.palette().color(QPalette.ColorRole.WindowText)
        brush = QBrush(text_color)

        for marker in self._chart.legend().markers():
            marker.setLabelBrush(brush)

    def changeEvent(self, event):
        if event.type() == event.Type.PaletteChange:
            self._update_legend_colors()
        super().changeEvent(event)
