import os
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (
                        QToolBar, QVBoxLayout, QPushButton,
                        QComboBox, QLabel, QHBoxLayout
                        )
from PyQt6.QtCore import QSize

here = os.path.dirname(os.path.abspath(__file__))

def newIcon(icon):
    icons_dir = os.path.join(here, "../icons")
    return QIcon(os.path.join(":/", icons_dir, f"{icon}.png"))
    
def newButton(
    text, 
    func=None,
    icon=None
):
    btn = QPushButton(text)
    if icon is not None:
        btn.setIcon(newIcon(icon))
    if func is not None:
        btn.clicked.connect(func)
    return btn
    
def newAction(
    parent,
    text,
    func=None,
    shortcut=None,
    icon=None,
    tip=None,
    checkable=False,
    enabled=True,
    checked=False,
):
    action = QAction(str(text), parent)
    if icon is not None:
        action.setIcon(newIcon(icon))
        action.setText(str(text))
    if shortcut is not None:
        action.setShortcut(shortcut)
    if tip is not None:
        action.setToolTip(str(tip))
        action.setStatusTip(str(tip))
    if func is not None:
        action.triggered.connect(func)
    if checkable:
        action.setCheckable(True)
    action.setEnabled(enabled)
    action.setChecked(checked)
    return action

def addActions(widget, actions):
    for action in actions:
        if action is None:
            widget.addSeparator()
        elif all([isinstance(widget, QToolBar), any([isinstance(action, QComboBox), isinstance(action, QLabel)])]):
            widget.addWidget(action)
        elif isinstance(action, QAction):
            widget.addAction(action)
            
def addWidgets(obj, widgets):
    for widget in widgets:
        if widget is None:
            continue
        elif any([isinstance(obj, QVBoxLayout), isinstance(obj, QHBoxLayout)]):
            obj.addLayout(widget)
        else:
            obj.addWidget(widget)