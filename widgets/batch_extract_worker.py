import os, time
from PyQt6.QtCore import QThread, pyqtSignal

class BatchExtractWorker(QThread):
    # Progress percentage
    progress = pyqtSignal(int, int) # Progress signal (current_frame, total_frames)
    finished = pyqtSignal()
    
    def __init__(self, video_path, output_dir, start_frame, end_frame, frame_step, roi=None):
        super().__init__()
        self._running = False
        self.video_path = video_path
        self.output_dir = output_dir
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.frame_step = frame_step
        self.roi = roi
        
    def run(self):
        import cv2
        self._running = True
        cap = cv2.VideoCapture(self.video_path, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)
        current_frame = self.start_frame
        count = 0
        total_frames = 1 + (self.end_frame - self.start_frame) // self.frame_step
        
        while cap.isOpened() and current_frame <= self.end_frame and self._running:
            ret, frame = cap.read()
            if not ret:
                break
            if (current_frame - self.start_frame) % self.frame_step == 0:
                if self.roi:
                    x1, y1, x2, y2 = self.roi
                    frame = frame[y1:y2, x1:x2]
                fname = os.path.splitext(os.path.basename(self.video_path))[0]
                os.makedirs(self.output_dir, exist_ok=True)
                out_path = os.path.join(self.output_dir, f"{fname}_frame_{current_frame}.jpg")
                cv2.imwrite(out_path, frame)
                count += 1
            current_frame += 1
            self.progress.emit(count, total_frames)
            # time.sleep(0.01) # Add some delay
        cap.release()
        self.finished.emit()
        
    def stop(self):
        self._running = False