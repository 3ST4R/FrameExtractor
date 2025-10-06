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
    
    def __init__(self, parent, max_time, current_time, img_width, img_height, fps):
        super().__init__(parent)
        self.worker = None
        self.setWindowTitle("Batch Extract")
        self.setWindowIcon(newIcon("batch"))
        self.resize(250, 350)
        
        self.img_width = img_width
        self.img_height = img_height
        self.current_time = current_time
        self.max_time = max_time
        self.fps = fps
        
        layout = QVBoxLayout(self)
        
        # Grid layout for uniform alignment
        grid = QGridLayout()
        
        # Start time
        grid.addWidget(QLabel("Start time: "), 0, 0) # Row 1, Column 1
        self.start_edit = QLineEdit(str(self.current_time))
        self.start_edit.setFixedWidth(80)
        self.start_edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.start_edit.setCursorPosition(0)
        grid.addWidget(self.start_edit, 0, 1) # Row 1, Column 2
        
        # End time
        grid.addWidget(QLabel("End time: "), 1, 0) # Row 2, Column 1
        self.end_edit = QLineEdit(str(self.max_time))
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
        try:
            params = self.get_params()
            if not params:
                return
            self.extract_btn.setEnabled(False)
            self.batch_extract_triggered.emit(params)
        except Exception as e:
            logger.error(f"{e}")
            QMessageBox.warning(self, "Error", f"{e}")
            
    def on_finished(self):
        self.extract_btn.setEnabled(True)
        QMessageBox.information(self, "Batch Extract", "Extraction complete!")
        logger.debug("Batch Extraction completed")
        
    def get_params(self):
        """Return dictionary of user-entered parameters with validation"""
        error_conditions = {}
        try:
            time_vals = []
            labels = ['Start time', 'End time']
            # Validate and set time inputs to HH:MM:SS[.ff]
            time_edits = (self.start_edit, self.end_edit)
            for idx, time_edit in enumerate(time_edits):
                text = time_edit.text()
                # Round frames per sec if present
                m = re.match(r'^(\d{1,2}:\d{2}:\d{2})(\.\d{2,3})?$', text)
                error_conditions[f"Time '{text}' for '{labels[idx]}' is invalid. Please use HH:MM:SS format."] = not bool(m)
                if not m:
                    time_vals.append(None)
                else:
                    time_edit.setText(m.group(0))
                    time_vals.append(time_edit.text().strip())
            
            start_time = str(self.current_time) if time_vals[0] is None else time_vals[0]
            end_time = str(self.max_time) if time_vals[1] is None else time_vals[1]

            start_secs = self.hms_to_secs(start_time, self.fps)
            end_secs = self.hms_to_secs(end_time, self.fps)
            error_conditions["'Start time' must be less than 'End time'"] = not start_secs < end_secs
            
            # Frame step validation
            frame_step = self.step_edit.text().strip()
            error_conditions["'Frame step' must be an integer"] = not self.is_int(frame_step)
            if self.is_int(frame_step):
                frame_step = int(frame_step)
            else:
                frame_step = 1
            condition = frame_step >= 1
            error_conditions["'Frame step' must be >= 1"] = not condition
            if not condition:
                frame_step = 1
            
            # ROI coords validation
            roi = None
            if self.crop_roi_chkbx.isChecked():
                invalid_roi_val = False
                roi_vals = []
                for idx, edit in enumerate(self.roi_edits):
                    val = edit.text().strip()
                    condition = self.is_int_float(val)
                    error_conditions[f"'{['x1','y1','x2','y2'][idx]}' must be an integer"] = not condition
                    if not condition:
                        invalid_roi_val = True
                    else:
                        roi_vals.append(int(float(val)))
                        
                if not invalid_roi_val and len(roi_vals) == 4:
                    roi = tuple(roi_vals)
                    error_conditions.update({
                        "x1 must be less than x2": not roi[0] < roi[2],
                        "y1 must be less than y2": not roi[1] < roi[3],
                        "x1 must be equal to or more than 0": not roi[0] >= 0,
                        "y1 must be equal to or more than 0": not roi[1] >= 0,
                        "x2 must be more than 0": not roi[2] > 0,
                        "y2 must be more than 0": not roi[3] > 0,
                        "x1 must be less than image width": not roi[0] < self.img_width,
                        "y1 must be less than image height": not roi[1] < self.img_height,
                        "x2 must be less than or equal to image width": not roi[2] <= self.img_width,
                        "y2 must be less than or equal to image height": not roi[3] <= self.img_height
                    })
                    
            # Log validation checks if errors found        
            errors = [msg for msg, con in error_conditions.items() if con]
            if errors:
                for err in errors:
                    logger.error(err)
                if len(errors) > 1:
                    errors = [f'{i}) ' + msg for i, msg in enumerate(errors, 1)]
                raise ValueError('\n'.join(errors))
            
            return dict(
                start_time=start_time,
                end_time=end_time,
                frame_step=frame_step,
                roi=roi
            )
        except ValueError as e:
            QMessageBox.warning(self, "Invalid input", f"Invalid input:\n{e}")
            return None
        except Exception as e:
            QMessageBox.warning(self, "Error", f"{e}")
            return None
            
    def is_int_float(self, string: str):
        int_bool = False
        float_bool = False
        try:
            int(string)
            int_bool = True
        except ValueError:
            pass
        try:
            float(string)
            float_bool = True
        except ValueError:
            pass
        return int_bool or float_bool
        
    def is_int(self, string: str):
        try:
            int_val = int(string)
            return isinstance(int_val, int)
        except ValueError:
            return False
            
    def hms_to_secs(self, hms_str, fps):
        h, m, sf = hms_str.split(":")
        if '.' in sf:
            s, f = map(int, sf.split('.'))
        else:
            s, f = map(int, (sf, 0))
        return int(h)*3600 + int(m)*60 + s + (f/fps)

