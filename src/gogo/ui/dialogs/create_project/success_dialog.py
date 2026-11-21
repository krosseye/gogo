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

from gogo.ui.components.sliding_label import SlidingLabel


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

        self.title_label = QLabel(
            f"Your new project '<b>{project_name}</b>' has been created successfully!"
        )
        self.title_label.setWordWrap(True)

        self.path_label = SlidingLabel()
        self.path_label.setFixedWidth(250)
        self.path_label.setStyleSheet("color: #888;")
        self.path_label.setText(project_path)

        self.text_container.addWidget(self.title_label)
        self.text_container.addWidget(QLabel("It can be found at:"))
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

        self.ok_button = QPushButton("Got it!")
        self.ok_button.setFixedWidth(100)
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        self.main_layout.addWidget(
            self.ok_button, alignment=Qt.AlignmentFlag.AlignRight
        )
