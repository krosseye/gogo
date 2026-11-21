import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QVBoxLayout,
)

from gogo.ui.components.elided_label import ElidedLabel


class ProjectCreatedDialog(QDialog):
    """Confirms a project was created: status icon | name and path | project icon."""

    def __init__(self, project_name, project_path, project_icon_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("Project Created")
        self.setFixedSize(450, 150)

        self.main_layout = QVBoxLayout(self)

        self.content_layout = QHBoxLayout()

        self.status_icon = QLabel()
        pixmap_type = QStyle.StandardPixmap.SP_MessageBoxInformation
        success_pixmap = self.style().standardIcon(pixmap_type).pixmap(48, 48)
        self.status_icon.setPixmap(success_pixmap)
        self.status_icon.setFixedSize(48, 48)
        self.content_layout.addWidget(
            self.status_icon,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )

        self.text_container = QVBoxLayout()

        self.title_label = QLabel(f"Created <b>{project_name}</b>.")
        self.title_label.setWordWrap(True)

        self.path_label = ElidedLabel(project_path)
        self.path_label.setMinimumWidth(250)

        self.text_container.addWidget(self.title_label)
        self.text_container.addWidget(QLabel("Location:"))
        self.text_container.addWidget(self.path_label)

        self.content_layout.addLayout(self.text_container, 3)

        self.proj_icon = QLabel()
        if os.path.exists(project_icon_path):
            self.proj_icon.setPixmap(
                QPixmap(project_icon_path).scaled(
                    48,
                    48,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            pixmap_type = QStyle.StandardPixmap.SP_FileDialogNewFolder
            fallback = self.style().standardIcon(pixmap_type).pixmap(48, 48)
            self.proj_icon.setPixmap(fallback)

        self.content_layout.addWidget(self.proj_icon, 0, Qt.AlignmentFlag.AlignCenter)

        self.main_layout.addLayout(self.content_layout)

        self.ok_button = QPushButton("OK")
        self.ok_button.setFixedWidth(100)
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        self.main_layout.addWidget(
            self.ok_button, alignment=Qt.AlignmentFlag.AlignRight
        )
