import re
from loguru import logger
from FrameExtractor.utils import newIcon
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QGroupBox, QPushButton, QProgressBar, QMessageBox, QGridLayout,
    QSpacerItem, QSizePolicy, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal

class BatchExtractDialog(QDialog):
    batch_extract_triggered = pyqtSignal(dict)
    
    def __init__(self, parent, max_time, current_time):
        super().__init__(parent)
        self.worker = None
        self.setWindowTitle("Batch Extract")
        self.setWindowIcon(newIcon("batch"))
        self.resize(250, 350)
        
        layout = QVBoxLayout(self)
        
        # Grid layout for uniform alignment
        grid = QGridLayout()
        
        # Start time
        grid.addWidget(QLabel("Start time: "), 0, 0) # Row 1, Column 1
        self.start_edit = QLineEdit(str(current_time))
        self.start_edit.setFixedWidth(80)
        self.start_edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.start_edit.setCursorPosition(0)
        grid.addWidget(self.start_edit, 0, 1) # Row 1, Column 2
        
        # End time
        grid.addWidget(QLabel("End time: "), 1, 0) # Row 2, Column 1
        self.end_edit = QLineEdit(str(max_time))
        self.end_edit.setFixedWidth(80)
        self.end_edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.end_edit.setCursorPosition(0)
        grid.addWidget(self.end_edit, 1, 1) # Row 2, Column 2
        
        # Frame step
        grid.addWidget(QLabel("Frame step: "), 2, 0) # Row 3, Column 1
        self.step_edit = QLineEdit("1")
        self.step_edit.setFixedWidth(80)
        grid.addWidget(self.step_edit, 2, 1) # Row 3, Column 2
        
        # Dummy widget for 3rd column
        spacer0 = QWidget()
        spacer0.setFixedWidth(80)
        grid.addWidget(spacer0, 0, 2) # Row 1, Column 3
        
        # Adding final grid to our layout
        layout.addLayout(grid)
        
        # Dummy widget for space
        spacer1 = QWidget()
        spacer1.setFixedHeight(20)
        layout.addWidget(spacer1)
        
        # Crop ROI group
        self.crop_roi_chkbx = QCheckBox("Crop ROI")
        layout.addWidget(self.crop_roi_chkbx)
        
        self.roi_group = QGroupBox()
        roi_grid = QGridLayout()
        # x1, y1, x2, y2
        roi_labels = ["x1: ", "y1: ", "x2: ", "y2: "]
        self.roi_edits = []
        
        for i, label in enumerate(roi_labels):
            roi_grid.addWidget(QLabel(label), i, 0)
            line_edit = QLineEdit()
            line_edit.setFixedWidth(70)
            roi_grid.addWidget(line_edit, i, 1)
            self.roi_edits.append(line_edit)
        # Dummy widget for 3rd column
        spacer2 = QWidget()
        spacer2.setFixedWidth(110)
        roi_grid.addWidget(spacer2, 0, 2) # Row 1, Column 3
        self.roi_group.setLayout(roi_grid)
        layout.addWidget(self.roi_group)
        
        # Disable ROI group (default)
        self.roi_group.setEnabled(False)
        
        # Checkbox connection to enable/disable ROI group
        self.crop_roi_chkbx.toggled.connect(self.roi_group.setEnabled)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Progress status label
        self.p_status = QLabel("")
        self.p_status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.p_status)
        
        # Spacer to push buttons down
        layout.addSpacerItem(QSpacerItem(10, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        self.extract_btn = QPushButton("Extract")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(self.extract_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        # Connect buttons
        self.extract_btn.clicked.connect(self.on_extract_clicked)
        cancel_btn.clicked.connect(self.on_cancel_clicked)
        
    def set_worker(self, worker):
        self.worker = worker
        
    def on_cancel_clicked(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        self.reject()
        
    def update_progress(self, current_frame, total_frames):
        percent = int(100 * current_frame / total_frames) if total_frames > 0 else 0
        self.progress_bar.setValue(percent)
        self.p_status.setText(f"Extracting... [{current_frame}/{total_frames} frames]")
        
    def on_extract_clicked(self):
        # Validate and round time inputs to HH:MM:SS
        for time_edit in (self.start_edit, self.end_edit):
            text = time_edit.text()
            # Round frames per sec if present
            m = re.match(r'^(\d{1,2}:\d{2}:\d{2})(\.\d{2,3})?$', text)
            if not m:
                QMessageBox.warning(self, "Invalid input", f"Time '{text}' is invalid. Please use HH:MM:SS format.")
                return
            else:
                time_edit.setText(m.group(0))
                
        params = self.get_params()
        if not params:
            return
        self.extract_btn.setEnabled(False)
        self.batch_extract_triggered.emit(params)
        
    def on_finished(self):
        self.extract_btn.setEnabled(True)
        QMessageBox.information(self, "Batch Extract", "Extraction complete!")
        logger.debug("Batch Extraction completed")
        
    def get_params(self):
        """Return dictionary of user-entered parameters with validation"""
        try:
            start_time = self.start_edit.text()
            end_time = self.end_edit.text()
            frame_step = int(self.step_edit.text())
            if frame_step < 1:
                logger.error("Frame step must be >= 1")
                raise ValueError("Frame step must be >= 1")
            roi = None
            if self.crop_roi_chkbx.isChecked():
                try:
                    roi = tuple(int(edit.text()) for edit in self.roi_edits)
                except (ValueError, TypeError) as e:
                    logger.error(f"ROI inputs not in ('int', 'float'): {e}")
                    raise
                if not (roi[0] < roi[2] and roi[1] < roi[3]):
                    logger.error("Invalid ROI coordinates")
                    raise ValueError("Invalid ROI coordinates")
            return dict(
                start_time=start_time,
                end_time=end_time,
                frame_step=frame_step,
                roi=roi
            )
        except (ValueError, TypeError) as e:
            QMessageBox.warning(self, "Invalid input", f"Invalid input: {e}")
            return None