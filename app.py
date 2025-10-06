# -*- coding: utf-8 -*-
"""
Created on Sun Sep 28 12:39:36 2025

@author: singh
"""

import os, cv2, functools
# import gc, logging
from loguru import logger
# from PIL import Image
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QVBoxLayout, QMessageBox,
    QApplication, QFileDialog, QComboBox, QStatusBar, QSlider, 
)
from PyQt6.QtCore import Qt, QSize, QTimer, QEvent
from PyQt6.QtGui import QImage, QPixmap, QAction
from types import SimpleNamespace
from FrameExtractor import __appname__
from FrameExtractor import utils
from FrameExtractor.widgets import VideoLoadDialog, FrameReaderThread, BatchExtractDialog, BatchExtractWorker

# from pynvml import nvmlInit, nvmlDeviceGetCount, nvmlShutdown, NVMLError
# def is_gpu_available():
#     try:
#         nvmlInit()
#         dev_c = nvmlDeviceGetCount()
#         nvmlShutdown()
#         return dev_c > 0
#     except NVMLError:
#         return False

# def pil_resize(img_arr, img_size):
#     pil_img = Image.fromarray(img_arr)
#     pil_img = pil_img.resize(img_size, Image.LANCZOS)
#     return np.array(pil_img)



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # self.setup_logging()
        self.setWindowTitle(__appname__)
        screen = QApplication.primaryScreen()
        screen_size = screen.availableGeometry()

        # Calculate width/height as a percentage of screen size (e.g., 80%)
        height = int(screen_size.height() * 0.7)
        width = int(height * 16 / 9)
        
        self.imsize = SimpleNamespace(width=max(width, 640), 
                                      height=max(height, 360))
        self.iconsize = SimpleNamespace(width=32,
                                      height=32)
        self.video_path = None
        self.output_dir = os.getcwd()
        self.cap = None
        self.frame_rate = 30
        self.frame_count = 0
        self.current_frame = 0
        self.time_step = 1 / self.frame_rate
        self.thread = None
        self.current_qimg = None
        self.video_paused = False
        self.seekbar_moving = False
        self.status_priority = False
        
        # Disable maximizing window
        flags = self.windowFlags()
        flags &= ~Qt.WindowType.WindowMaximizeButtonHint
        self.setWindowFlags(flags)
        
        self.setup_ui()
        QTimer.singleShot(0, self.lock_window_size)
        
        # Timer to update frame from buffer for smooth playback
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_from_buffer)
        
        # Timer to rolling back to default status message
        self.default_status_timer = QTimer()
        self.default_status_timer.setSingleShot(True)
        self.default_status_timer.timeout.connect(self.reset_status_priority)
        
        self.activateWindow()
        self.raise_()
        self.setFocus()

    def setup_ui(self):
        # Toolbar
        self.toolbar = utils.ToolBar("Toolbar")
        self.toolbar.setIconSize(QSize(self.iconsize.width, self.iconsize.height))
        # self.toolbar.setStyleSheet("font-size: 9pt;")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.toolbar.setMovable(False)
        self.toolbar.installEventFilter(self)
        self.toolbar.visibilityChanged.connect(self.sync_toggle_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)
        
        # Menubar
        self.menubar = self.menuBar()
        self.menubar.installEventFilter(self)
        self.menus = SimpleNamespace(
            file=self.menubar.addMenu("File"),
            edit=self.menubar.addMenu("Edit"),
            view=self.menubar.addMenu("View")
        )
        
        # Actions
        selfAction = functools.partial(utils.newAction, self)
        load = selfAction(
                "Load\nVideo",
                self.load_video,
                "Ctrl+O",
                "open",
                "Load a video"
                )
        outdir = selfAction(
                text="Change\nOutput Dir",
                func=self.change_output_dir,
                icon="open",
                tip="Change Output Directory"
                )
        save = selfAction(
                "Save\nFrame",
                self.save_frame,
                "Ctrl+S",
                "save",
                "Save the current frame"
                )
        reset = selfAction(
                "Reset\nApp",
                self.reset_state,
                "Ctrl+R",
                "delete",
                "Reset application for new video"
                )
        quit_ = selfAction(
                text="Quit",
                func=self.close_window,
                icon="quit",
                tip="Quit application"
                )
        rewind = selfAction(
                "Rewind",
                self.rewind_video,
                "Left",
                "prev",
                "Rewind the video"
                )
        forward = selfAction(
                "Forward",
                self.forward_video,
                "Right",
                "next",
                "Forward the video"
                )
        self.toggleToolbar = selfAction(
                text="Toolbar",
                func=self.toggle_toolbar,
                tip="Show/hide the toolbar",
                checkable=True,
                checked=True
                )
        batch_extract = selfAction(
                "Batch\nExtract",
                self.open_batch_extract_dialog,
                None,
                "batch",
                "Batch extract frames with optional ROI cropping"
                )
        # Custom Play/Pause
        self.play_pause = QAction(self)
        
        self.play_icons = {
            "no_video": utils.newIcon("play_pause"),
            "play": utils.newIcon("play"),
            "pause": utils.newIcon("pause")
        }
        self.set_play_pause_state("no_video")
        self.play_pause.setShortcut("Space")
        self.play_pause.triggered.connect(self.toggle_play_pause)
        
        # Time Combobox
        self.time_cb = QComboBox()
        self.time_cb.addItems(['1 frame', '0.1 second', '0.25 second', '0.5 second', '1 second', '2 seconds', '5 seconds', '10 seconds'])
        self.time_cb.setCurrentIndex(0)
        self.time_cb.currentTextChanged.connect(self.on_combobox_changed)
        # QTimer.singleShot(0, lambda: self.on_combobox_changed(self.time_cb.currentText()))
        self.time_cb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        # Time and frame labels
        self.time_label = QLabel(" Time: 00:00:00.00 ")
        self.frame_label = QLabel(" Frame: 0 ")

        # Adding menu actions
        utils.addActions(
            self.menus.file,
            (
                load,
                outdir,
                save,
                quit_,
            )
        )
        utils.addActions(
            self.menus.edit,
            (
                self.play_pause,
                None,
                rewind,
                forward,
                None,
                batch_extract,
                None,
                reset
            )
        )
        utils.addActions(
            self.menus.view,
            (
                self.toggleToolbar,
            )
        )
        
        # Adding toolbar actions
        utils.addActions(
           self.toolbar,
            (
                load,
                outdir,
                self.play_pause,
                save,
                reset,
                None,
                rewind,
                forward,
                None,
                batch_extract,
                None,
                QLabel(" Forward/Rewind by: "),
                self.time_cb,
                QLabel(" "),
                None,
                self.time_label,
                None,
                self.frame_label
            )
        )

        # Central widget (canvas + seekbar)
        central_widget = QWidget()
        layout = QVBoxLayout()
        self.canvas = QLabel("Load a video")
        self.canvas.setFixedSize(self.imsize.width, self.imsize.height)
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setStyleSheet("font-size: 32pt;")
        layout.addWidget(self.canvas)
        
        # Seekbar for frame navigation
        self.seekbar = QSlider(Qt.Orientation.Horizontal)
        self.seekbar.setMinimum(0)
        self.seekbar.setMaximum(0)
        self.seekbar.setTickPosition(QSlider.TickPosition.NoTicks)
        self.seekbar.sliderPressed.connect(self.on_seek_pressed)
        self.seekbar.sliderReleased.connect(self.on_seek_released)
        self.seekbar.sliderMoved.connect(self.on_seek_moved)
        self.seekbar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.seekbar)
        
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        
        self.update_log()
        self.update_status()
        
    def update_status(self):
        if getattr(self, 'status_priority', False):
            return
        if self.video_paused:
            self.status.showMessage("Video is paused!")
        else:
            self.status.showMessage(f"Output Dir: {self.output_dir}")
            
    def reset_status_priority(self):
        self.status_priority = False
        self.update_status()
        
    def update_log(self):
        logger.info(f"Output Dir: '{self.output_dir}'")
        
    def reset_state(self):
        # Stop thread if running
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread = None
        if self.cap:
            self.cap.release()
            self.cap = None
        # Reset state
        self.setWindowTitle(__appname__)
        self.video_path = None
        self.current_frame = 0
        self.frame_count = 0
        self.frame_rate = 30
        self.current_qimg = None
        self.seekbar.setMinimum(0)
        self.seekbar.setMaximum(0)
        self.seekbar.setValue(0)
        self.canvas.setPixmap(QPixmap())  # Clear any displayed frames
        self.canvas.setText("Load a video")
        self.time_label.setText(" Time: 00:00:00.00 ")
        self.frame_label.setText(" Frame: 0 ")
        self.update_status()
        if hasattr(self, 'play_pause'):
            self.set_play_pause_state("no_video")
            
    def set_play_pause_state(self, state):
        if state == "no_video":
            self.play_pause.setIcon(self.play_icons["no_video"])
            self.play_pause.setText("Play\nPause")
            self.play_pause.setToolTip("Play/Pause the video")
            self.play_pause.setStatusTip("Play/Pause the video")
            self.video_paused = False
        elif state == "play":
            self.play_pause.setIcon(self.play_icons["play"])
            self.play_pause.setText("Play\nVideo")
            self.play_pause.setToolTip("Play the video")
            self.play_pause.setStatusTip("Play the video")
            self.video_paused = True
        elif state == "pause":
            self.play_pause.setIcon(self.play_icons["pause"])
            self.play_pause.setText("Pause\nVideo")
            self.play_pause.setToolTip("Pause the video")
            self.play_pause.setStatusTip("Pause the video")
            self.video_paused = False

    def load_video(self):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread = None
            self.set_play_pause_state("play")
            
        if self.cap:
            self.cap.release()
            self.cap = None

        file_path, _ = VideoLoadDialog.getOpenFileName(self)
        if file_path:
            self.video_path = file_path
            self.status_priority = True
            self.cap = cv2.VideoCapture(self.video_path, cv2.CAP_FFMPEG)
            if not self.cap.isOpened():
                logger.error(f"Failed to open video: {os.path.basename(self.video_path)}")
                self.status.showMessage("Failed to open video")
                self.default_status_timer.start(3000) # after 3 seconds reset to default message
                return
            self.frame_rate = self.cap.get(cv2.CAP_PROP_FPS)
            self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.current_frame = 0
            self.seekbar.setMaximum(self.frame_count - 1)
            self.show_frame(self.current_frame)
            self.setWindowTitle(f"{__appname__} - {os.path.basename(self.video_path)}")
            self.set_play_pause_state("play")
            self.on_combobox_changed(self.time_cb.currentText())
            logger.info(f"Video loaded: {os.path.basename(self.video_path)}, FPS: {self.frame_rate:.2f}")
            self.status.showMessage(f"Video: {os.path.basename(self.video_path)} | FPS: {self.frame_rate:.2f}")
            self.default_status_timer.start(3000) # after 3 seconds reset to default message
            
    def change_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_dir = directory
            logger.info(f"Output Dir changed to: '{self.output_dir}'")
            self.update_status()

    def on_combobox_changed(self, val):
        if val == "1 frame":
            self.time_step = 1 / self.frame_rate
        else:
            self.time_step = float(val.split(' ')[0])

    def replay_thread(self, start=0):
        if not self.cap or not self.cap.isOpened():
            return
        
        if self.thread is not None and self.thread.isRunning():
            self.thread.stop()
            self.thread = None
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        self.thread = FrameReaderThread(self.cap, start)
        self.thread.frame_ready.connect(self.handle_frame)
        self.thread.start()
        self.set_play_pause_state("pause")
        self.timer.start(int(1000 / self.frame_rate))

    def toggle_play_pause(self):
        if not self.video_path:
            return
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread = None
            self.set_play_pause_state("play")
            self.timer.stop()
        else:
            self.replay_thread(self.current_frame)
        self.update_status()
            
    def toggle_toolbar(self, checked):
        if checked:
            self.toolbar.show()
        else:
            self.toolbar.hide()
        self.update_status()
        
    def sync_toggle_toolbar(self, checked):
        self.toggleToolbar.setChecked(checked)
        
    def open_batch_extract_dialog(self):
        if not self.cap:
            QMessageBox.information(self, __appname__, "Please load a video first.")
            return
        try:
            max_secs = self.frame_count / self.frame_rate if self.frame_rate else 0
            max_time_str = self.format_time(max_secs, self.frame_rate)
            current_secs = self.current_frame / self.frame_rate if self.frame_rate else 0
            current_time_str = self.format_time(current_secs, self.frame_rate)
            
            frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
            dialog = BatchExtractDialog(self, max_time=max_time_str, current_time=current_time_str, img_width=frame_width, img_height=frame_height, fps=self.frame_rate)
            # Run batch extract with params, show progress
            dialog.batch_extract_triggered.connect(lambda params: self.run_batch_extract(params, dialog))
            dialog.exec()
        except Exception as e:
            logger.error(f"{e}")
            QMessageBox.warning(self, "Error", f"{e}")
        
            
    def hms_to_secs(self, hms_str, fps):
        h, m, sf = hms_str.split(":")
        if '.' in sf:
            s, f = map(int, sf.split('.'))
        else:
            s, f = map(int, (sf, 0))
        return int(h)*3600 + int(m)*60 + s + (f/fps)
        
    def format_time(self, seconds, fps):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        f = int((seconds - int(seconds)) * fps)
        return f"{h:02d}:{m:02d}:{s:02d}.{f:02d}"
    
    def run_batch_extract(self, params, dialog):
        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        output_dir = os.path.join(self.output_dir, video_name, "batch_extract")
        
        start_secs = self.hms_to_secs(params['start_time'], self.frame_rate)
        end_secs = self.hms_to_secs(params['end_time'], self.frame_rate)
        start_frame = int(start_secs * self.frame_rate)
        end_frame = int(end_secs * self.frame_rate)
        
        # Ensure start and end is within video length
        start_frame = max(0, min(start_frame, self.frame_count - 1))
        end_frame = max(0, min(end_frame, self.frame_count - 1))
        
        self.batch_worker = BatchExtractWorker(
            self.video_path,
            output_dir,
            start_frame,
            end_frame,
            params['frame_step'],
            params.get('roi')
        )
        dialog.set_worker(self.batch_worker)
        self.batch_worker.progress.connect(dialog.update_progress)
        self.batch_worker.finished.connect(dialog.on_finished)
        self.batch_worker.start()
        logger.debug("Batch Extraction started")

    def handle_frame(self, qimage, frame_idx):
        # Display as frames are buffered by thread
        self.current_qimg = None
        self.current_qimg = qimage
        self.current_frame = frame_idx
        pixmap = QPixmap.fromImage(qimage).scaled(self.canvas.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.canvas.setPixmap(pixmap)
        self.update_labels()
        self.seekbar.setValue(frame_idx)
        # Stop automatically at last frame
        if self.current_frame >= self.frame_count - 1:
            self.toggle_play_pause()
            self.timer.stop()
            
    def update_from_buffer(self):
        # Timer handler to grab frames from prefetch buffer and display
        if self.thread:
            frame_data = self.thread.get_frame()
            if frame_data:
                qimg, frame_idx = frame_data
                self.handle_frame(qimg, frame_idx)

    def show_frame(self, frame_idx, update_state=True):
        # Frame display
        # update_state=False : For non-playing mode, read single frame (blocking)
        # update_state=True : No thread stoppage or play state change
        if not self.video_path or not self.cap:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = self.cap.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(qimg).scaled(self.canvas.size(), Qt.AspectRatioMode.KeepAspectRatio)
            self.canvas.setPixmap(pixmap)
            self.current_qimg = qimg
            if update_state:
                self.current_frame = frame_idx
            self.update_labels()

    def rewind_video(self):
        new_frame = max(0, self.current_frame - int(self.time_step * self.frame_rate))
        self.pause_and_show_frame(new_frame)
        self.update_status()

    def forward_video(self):
        new_frame = min(self.frame_count - 1, self.current_frame + int(self.time_step * self.frame_rate))
        self.pause_and_show_frame(new_frame)
        self.update_status()

    def pause_and_show_frame(self, frame_idx):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread = None
            self.set_play_pause_state("play")
            self.timer.stop()
        self.show_frame(frame_idx)
        
    # def setup_logging(self):
    #     logging.basicConfig(
    #         filename="frame_extractor.log",
    #         level=logging.DEBUG,
    #         format="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s",
    #         datefmt="%Y-%m-%d %H:%M:%S"
    #     )
    #     self.logger = logging.getLogger()
        
    def on_seek_pressed(self):
        self.seekbar_moving = True
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread = None
            self.set_play_pause_state("play")
            self.update_status()
            self.timer.stop()
            
    def on_seek_released(self):
        self.seekbar_moving = False
        frame_idx = self.seekbar.value()
        self.show_frame(frame_idx)
        self.current_frame = frame_idx
        # Resume playback after release
        self.replay_thread(frame_idx)
        self.update_status()
        
    def on_seek_moved(self, value):
        if self.seekbar_moving:
            # show frame when dragging
            self.show_frame(value, update_state=False)
        self.update_status()

    def update_labels(self):
        total_sec = self.current_frame / self.frame_rate if self.frame_rate else 0
        self.time_label.setText(f" Time: {self.format_time(total_sec, self.frame_rate)} ")
        self.frame_label.setText(f" Frame: {self.current_frame} ")
        if not self.seekbar_moving:
            self.seekbar.setValue(self.current_frame)

    def save_frame(self):
        if self.current_qimg and not (self.thread and self.thread.isRunning()):
            video_name = os.path.splitext(os.path.basename(self.video_path))[0]
            save_dir = os.path.join(self.output_dir, video_name)
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, f"{video_name}_frame_{self.current_frame}.jpg")
            self.current_qimg.save(save_path)
            self.status_priority = True
            logger.info(f"Frame saved to {save_path}")
            self.status.showMessage(f"Frame saved to {save_path}")
            self.default_status_timer.start(3000) # after 3 seconds reset to default message
            
    def close_window(self):
        logger.info("Exiting...")
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread = None
        if self.cap:
            self.cap.release()
            self.cap = None
        self.close()
        
    def closeEvent(self, ev):
        self.close_window()
        ev.accept()
        
    def eventFilter(self, source, ev):
        if ev.type() == QEvent.Type.Leave and (source == self.menubar or source == self.toolbar):
            self.update_status()
        return super().eventFilter(source, ev)
        
    def lock_window_size(self):
        # Lock current window size
        self.setFixedSize(self.size())

