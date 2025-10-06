import cv2, queue
from threading import Event
from PyQt6.QtGui import QImage
from PyQt6.QtCore import QThread, pyqtSignal

class FrameReaderThread(QThread):
    frame_ready = pyqtSignal(QImage, int)  # signal emits QImage and frame index

    def __init__(self, cap, start_frame=0, max_queue_size=30):
        super().__init__()
        self.cap = cap
        self.running = False
        self.start_frame = start_frame
        self.current_frame = start_frame
        self.frame_queue = queue.Queue(maxsize=max_queue_size)
        self.stopped = Event()
        
    def run(self):
        self.running = True
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)
        self.current_frame = self.start_frame
        while self.running and not self.stopped.is_set():
            if self.frame_queue.full():
                self.msleep(5) # wait to reduce CPU load when queue full
                continue
            ret, frame = self.cap.read()
            if not ret:
                break
            # Convert to RGB and QImage
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            # Create QImage directly from RGB data (avoid copies if possible)
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            self.frame_queue.put((qimg, self.current_frame))
            self.current_frame += 1
        self.running = False

    def stop(self):
        self.running = False
        self.stopped.set()
        self.wait()
        
    def get_frame(self):
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None