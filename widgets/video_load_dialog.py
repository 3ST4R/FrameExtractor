from PyQt6.QtWidgets import QFileDialog, QPushButton

class VideoLoadDialog(QFileDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFileMode(QFileDialog.FileMode.ExistingFile)
    
    @staticmethod
    def getOpenFileName(parent=None, caption=None, directory="", filter=None):
        if caption is None:
            caption = "Load Video"
        if filter is None:
            filter = "Video Files (*.mp4 *.avi *.mkv *.mov *.flv *.webm *.wmv *.mpeg *.mpg *.m4v)"
            
        dialog = VideoLoadDialog(parent)
        dialog.setWindowTitle(caption)
        dialog.setNameFilter(filter)
        if directory:
            dialog.setDirectory(directory)
        if dialog.exec():
            return dialog.selectedFiles()[0], dialog.selectedNameFilter()
        return '', ''