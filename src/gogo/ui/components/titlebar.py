from PySide6.QtWidgets import QHBoxLayout, QLabel, QLayout, QWidget


class TitleBar(QWidget):
    """A tab's heading row: its title on the left, its tools on the right."""

    def __init__(
        self,
        title: str,
        children: list[QLayout | QWidget] | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.setFixedHeight(40)

        self.title_label = QLabel(f"<h2>{title}</h2>", self)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self.title_label)
        self._layout.addStretch(1)

        for child in children or []:
            if isinstance(child, QWidget):
                self._layout.addWidget(child)
            elif isinstance(child, QLayout):
                self._layout.addLayout(child)
