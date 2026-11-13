import sys
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog, QComboBox,
    QTextEdit, QDoubleSpinBox, QMessageBox)
from core import init_db, register, recordings, verify

DB = Path.home() / '.resonanceauth' / 'references.sqlite3'
DB.parent.mkdir(parents=True, exist_ok=True)
init_db(DB)

class Worker(QObject):
    done = Signal(object)
    failed = Signal(str)
    finished = Signal()
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
    def run(self):
        try:
            self.done.emit(self.operation())
        except Exception as exc:
            self.failed.emit(f'{type(exc).__name__}: {exc}')
        finally:
            self.finished.emit()

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ResonanceAuth — Desktop Prototype')
        self.resize(760, 560)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.addWidget(QLabel('<h2>ResonanceAuth</h2>'))
        layout.addWidget(QLabel('Local prototype • fingerprints remain in your local SQLite database'))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText('Song title')
        layout.addWidget(self.title_edit)
        self.register_path = QLineEdit()
        self.register_path.setReadOnly(True)
        layout.addLayout(self.path_row('Original recording', self.register_path))
        self.register_btn = QPushButton('Register and sign recording')
        self.register_btn.clicked.connect(self.do_register)
        layout.addWidget(self.register_btn)
        layout.addWidget(QLabel('<h3>Verify a recording</h3>'))
        self.choice = QComboBox()
        layout.addWidget(self.choice)
        self.verify_path = QLineEdit()
        self.verify_path.setReadOnly(True)
        layout.addLayout(self.path_row('Recording to check', self.verify_path))
        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel('Experimental cosine threshold:'))
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(-1, 1)
        self.threshold.setDecimals(2)
        self.threshold.setSingleStep(0.05)
        self.threshold.setValue(0.90)
        threshold_row.addWidget(self.threshold)
        threshold_row.addStretch()
        layout.addLayout(threshold_row)
        self.verify_btn = QPushButton('Verify selected recording')
        self.verify_btn.clicked.connect(self.do_verify)
        layout.addWidget(self.verify_btn)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.refresh()

    def path_row(self, label, field):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        row.addWidget(field, 1)
        button = QPushButton('Browse…')
        button.clicked.connect(lambda: self.pick_file(field))
        row.addWidget(button)
        return row

    def pick_file(self, field):
        path, _ = QFileDialog.getOpenFileName(self, 'Select audio file', '',
                                               'Audio files (*.wav *.mp3 *.flac *.ogg *.m4a);;All files (*)')
        if path:
            field.setText(path)

    def refresh(self):
        self.choice.clear()
        for record_id, title in recordings(DB):
            self.choice.addItem(f'{title} (ID {record_id})', record_id)

    def start_work(self, operation, on_done):
        self.register_btn.setEnabled(False)
        self.verify_btn.setEnabled(False)
        self.output.setPlainText('Processing audio…')
        # Keep references until Qt signals that the thread has stopped.
        self.thread = QThread(self)
        self.worker = Worker(operation)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        # Window methods are QObject slots: queued delivery updates widgets only
        # on the GUI thread, even when emitted from the worker thread.
        self.worker.done.connect(on_done)
        self.worker.failed.connect(self.work_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.enable_buttons)
        self.thread.start()

    @Slot(str)
    def work_failed(self, message):
        self.output.setPlainText('Error: ' + message)

    @Slot()
    def enable_buttons(self):
        self.register_btn.setEnabled(True)
        self.verify_btn.setEnabled(True)

    def do_register(self):
        title, path = self.title_edit.text(), self.register_path.text()
        if not title.strip() or not path:
            QMessageBox.warning(self, 'Missing information', 'Enter a song title and select original audio.')
            return
        self.start_work(lambda: register(DB, title, path), self.register_done)

    @Slot(object)
    def register_done(self, result):
        record_id, count = result
        self.refresh()
        self.output.setPlainText(f'Registered recording ID {record_id}\nSigned {count} segments.\n\n'
            'Demo caveat: keys are generated during registration; artist identity is NOT authenticated.')

    def do_verify(self):
        record_id, path = self.choice.currentData(), self.verify_path.text()
        if record_id is None or not path:
            QMessageBox.warning(self, 'Missing information', 'Choose a registered song and an audio file.')
            return
        tau = self.threshold.value()
        self.start_work(lambda: verify(DB, record_id, path, tau), self.verify_done)

    @Slot(object)
    def verify_done(self, results):
        lines = ['Reference signature: VALID (against stored key; artist identity not established)', '']
        for item in results:
            score = 'N/A' if item['similarity'] is None else f"{item['similarity']:.3f}"
            status = 'MATCH' if item['match'] else 'FLAGGED'
            lines.append(f"Segment {item['segment']} ({item['start_s']}–{item['end_s']}s): {score} — {status}")
        lines.append('\nNote: threshold is experimental; alignment and adversarial robustness are not established.')
        self.output.setPlainText('\n'.join(lines))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
