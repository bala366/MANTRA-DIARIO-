# -*- coding: utf-8 -*-
import os
import re
import sys
import threading
import traceback
from pathlib import Path
from datetime import datetime

# ---------- SELF TEST ----------
def self_test():
    import tkinter
    import requests
    import certifi
    import urllib3
    import idna
    import charset_normalizer
    import faster_whisper
    import ctranslate2
    import huggingface_hub
    import tokenizers
    import av
    import reportlab
    print("SELF_TEST_OK")
    return 0

if "--self-test" in sys.argv:
    raise SystemExit(self_test())

import tkinter as tk
from tkinter import ttk, messagebox

AUDIO_EXTS = {".mp3",".wav",".m4a",".aac",".flac",".ogg",".opus",".wma"}

def fmt_time(seconds):
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def downloads_folder():
    home = Path.home()
    candidates = [
        home / "Downloads",
        home / "Download",
        Path(os.environ.get("USERPROFILE", str(home))) / "Downloads",
        Path(os.environ.get("USERPROFILE", str(home))) / "Download",
    ]
    for p in candidates:
        if p.exists() and p.is_dir():
            return p
    return Path.cwd()

def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Transcritor de Áudio - Afirmações V4")
        self.geometry("1040x760")
        self.minsize(900, 640)

        self.downloads = downloads_folder()
        self.audio_files = []
        self.current_audio = None
        self.records = []
        self.is_transcribing = False
        self.stop_requested = False
        self.last_pdf = None

        self.build_ui()
        self.refresh_files()

    def build_ui(self):
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")

        ttk.Label(
            top,
            text="TRANSCRITOR DE ÁUDIO PARA PDF - V4",
            font=("Segoe UI", 18, "bold")
        ).pack(anchor="w")

        ttk.Label(
            top,
            text=f"Pasta de áudio e saída: {self.downloads}"
        ).pack(anchor="w", pady=(3, 0))

        box = ttk.LabelFrame(self, text="Áudio", padding=10)
        box.pack(fill="x", padx=12, pady=(0, 8))

        self.file_combo = ttk.Combobox(box, state="readonly", width=80)
        self.file_combo.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.file_combo.bind("<<ComboboxSelected>>", self.on_file_selected)

        ttk.Button(box, text="Atualizar", command=self.refresh_files).grid(row=0, column=1)
        ttk.Button(box, text="Abrir áudio", command=self.open_audio).grid(row=0, column=2, padx=(8, 0))
        box.columnconfigure(0, weight=1)

        opts = ttk.LabelFrame(self, text="Transcrição", padding=10)
        opts.pack(fill="x", padx=12, pady=(0, 8))

        ttk.Label(opts, text="Modelo:").grid(row=0, column=0, sticky="w")
        self.model_var = tk.StringVar(value="medium")
        self.model_combo = ttk.Combobox(
            opts,
            state="readonly",
            textvariable=self.model_var,
            values=["small", "medium", "large-v3"],
            width=16
        )
        self.model_combo.grid(row=0, column=1, sticky="w", padx=(8, 16))
        ttk.Label(opts, text="Recomendado: MEDIUM para voz misturada com música.").grid(row=0, column=2, sticky="w")

        buttons = ttk.Frame(self, padding=(12, 2))
        buttons.pack(fill="x")

        self.start_btn = ttk.Button(buttons, text="INICIAR TRANSCRIÇÃO", command=self.start)
        self.start_btn.pack(side="left")

        ttk.Button(buttons, text="PARAR", command=self.stop).pack(side="left", padx=8)
        ttk.Button(buttons, text="ABRIR PDF", command=self.open_pdf).pack(side="right")

        status = ttk.Frame(self, padding=(12, 6))
        status.pack(fill="x")

        self.status_var = tk.StringVar(value="Pronto.")
        ttk.Label(status, textvariable=self.status_var, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.progress = ttk.Progressbar(status, mode="indeterminate")
        self.progress.pack(fill="x", pady=(6, 0))

        frame = ttk.LabelFrame(self, text="Afirmações reconhecidas em tempo real", padding=8)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self.text = tk.Text(frame, wrap="word", font=("Segoe UI", 11))
        self.text.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(frame, command=self.text.yview)
        scroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=scroll.set)

        ttk.Label(
            self,
            text="O progresso é salvo a cada trecho. No final, TXT e PDF são gerados em Downloads.",
            padding=(12, 0, 12, 12)
        ).pack(anchor="w")

    def append(self, txt):
        self.text.insert("end", txt + "\n")
        self.text.see("end")

    def refresh_files(self):
        try:
            self.audio_files = sorted(
                [p for p in self.downloads.iterdir()
                 if p.is_file() and p.suffix.lower() in AUDIO_EXTS],
                key=lambda p: p.name.lower()
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível ler Downloads:\n{e}")
            self.audio_files = []

        names = [p.name for p in self.audio_files]
        self.file_combo["values"] = names

        if names:
            self.file_combo.current(0)
            self.current_audio = self.audio_files[0]
            self.status_var.set(f"{len(names)} áudio(s) encontrado(s).")
        else:
            self.current_audio = None
            self.status_var.set("Nenhum áudio encontrado em Downloads.")

    def on_file_selected(self, event=None):
        idx = self.file_combo.current()
        if 0 <= idx < len(self.audio_files):
            self.current_audio = self.audio_files[idx]
            self.status_var.set(f"Selecionado: {self.current_audio.name}")

    def open_audio(self):
        if not self.current_audio:
            return
        try:
            os.startfile(str(self.current_audio))
        except Exception as e:
            messagebox.showerror("Áudio", str(e))

    def start(self):
        if self.is_transcribing:
            return
        if not self.current_audio:
            messagebox.showwarning("Transcrição", "Selecione um áudio.")
            return

        self.is_transcribing = True
        self.stop_requested = False
        self.records = []
        self.last_pdf = None
        self.text.delete("1.0", "end")
        self.progress.start(10)
        self.start_btn.configure(state="disabled")
        self.file_combo.configure(state="disabled")
        self.model_combo.configure(state="disabled")

        threading.Thread(target=self.worker, daemon=True).start()

    def stop(self):
        if self.is_transcribing:
            self.stop_requested = True
            self.status_var.set("Parada solicitada. Aguarde o trecho atual terminar...")

    def worker(self):
        audio = self.current_audio
        model_name = self.model_var.get()
        progress_path = audio.with_name(audio.stem + "_PROGRESSO_TRANSCRICAO.txt")
        error_path = audio.with_name(audio.stem + "_ERRO_TRANSCRICAO.txt")

        try:
            self.after(0, lambda: self.status_var.set(
                f"Carregando modelo {model_name}. Na primeira vez pode demorar..."
            ))

            from faster_whisper import WhisperModel
            model = WhisperModel(model_name, device="cpu", compute_type="int8")

            self.after(0, lambda: self.status_var.set("Transcrevendo áudio..."))
            self.after(0, lambda: self.append(
                f"=== TRANSCRIÇÃO INICIADA | MODELO {model_name.upper()} ==="
            ))

            segments, info = model.transcribe(
                str(audio),
                language="pt",
                task="transcribe",
                beam_size=5,
                temperature=0.0,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=250,
                    speech_pad_ms=250
                ),
                condition_on_previous_text=True
            )

            with open(progress_path, "w", encoding="utf-8") as f:
                count = 0
                for seg in segments:
                    if self.stop_requested:
                        break

                    txt = clean_text(seg.text)
                    if not txt:
                        continue

                    count += 1
                    rec = {
                        "start": float(seg.start),
                        "end": float(seg.end),
                        "text": txt
                    }
                    self.records.append(rec)

                    line = f"{count:04d} | [{fmt_time(seg.start)} - {fmt_time(seg.end)}] {txt}"
                    f.write(line + "\n")
                    f.flush()

                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass

                    self.after(0, lambda s=line: self.append(s))
                    self.after(0, lambda c=count: self.status_var.set(
                        f"Transcrevendo... {c} trecho(s) reconhecido(s)"
                    ))

            if self.stop_requested:
                self.after(0, lambda: self.status_var.set(
                    "Interrompido. O progresso ficou salvo em Downloads."
                ))
                return

            if not self.records:
                raise RuntimeError("Nenhuma fala foi reconhecida.")

            txt_path = self.write_txt(audio, model_name)
            pdf_path = self.write_pdf(audio, model_name)
            self.last_pdf = pdf_path

            self.after(0, lambda: self.append("\n=== TRANSCRIÇÃO CONCLUÍDA ==="))
            self.after(0, lambda: self.status_var.set(
                f"Concluído. PDF gerado: {pdf_path.name}"
            ))
            self.after(0, lambda: messagebox.showinfo(
                "Concluído",
                f"TXT:\n{txt_path}\n\nPDF:\n{pdf_path}"
            ))

        except Exception as e:
            try:
                error_path.write_text(traceback.format_exc(), encoding="utf-8")
            except Exception:
                pass

            self.after(0, lambda: self.append("=== ERRO ===\n" + str(e)))
            self.after(0, lambda: self.status_var.set(
                "Erro. Veja *_ERRO_TRANSCRICAO.txt em Downloads."
            ))
            self.after(0, lambda: messagebox.showerror("Erro", str(e)))

        finally:
            self.is_transcribing = False
            self.after(0, self.progress.stop)
            self.after(0, lambda: self.start_btn.configure(state="normal"))
            self.after(0, lambda: self.file_combo.configure(state="readonly"))
            self.after(0, lambda: self.model_combo.configure(state="readonly"))

    def write_txt(self, audio, model_name):
        path = audio.with_name(audio.stem + "_AFIRMACOES_COMPLETAS.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("AFIRMAÇÕES TRANSCRITAS\n")
            f.write("=" * 90 + "\n")
            f.write(f"Arquivo: {audio.name}\n")
            f.write(f"Modelo: {model_name}\n")
            f.write(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("=" * 90 + "\n\n")
            for rec in self.records:
                f.write(rec["text"] + "\n")

            f.write("\n\nTRANSCRIÇÃO COM HORÁRIO\n")
            f.write("=" * 90 + "\n\n")
            for rec in self.records:
                f.write(
                    f"[{fmt_time(rec['start'])} - {fmt_time(rec['end'])}] "
                    f"{rec['text']}\n"
                )
        return path

    def write_pdf(self, audio, model_name):
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.enums import TA_CENTER
        from xml.sax.saxutils import escape

        path = audio.with_name(audio.stem + "_AFIRMACOES_TRANSCRITAS.pdf")
        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            leftMargin=1.7*cm,
            rightMargin=1.7*cm,
            topMargin=1.7*cm,
            bottomMargin=1.7*cm
        )

        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "title",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=14
        )
        body = ParagraphStyle(
            "body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            spaceAfter=7
        )
        small = ParagraphStyle(
            "small",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            spaceAfter=4
        )

        story = [
            Paragraph("AFIRMAÇÕES TRANSCRITAS DO ÁUDIO", title),
            Paragraph(f"<b>Arquivo:</b> {escape(audio.name)}", body),
            Paragraph(f"<b>Modelo:</b> {escape(model_name)}", body),
            Paragraph(
                f"<b>Gerado em:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                body
            ),
            Spacer(1, 10),
            Paragraph("<b>Texto completo</b>", body),
        ]

        for rec in self.records:
            story.append(Paragraph(escape(rec["text"]), body))

        story.append(PageBreak())
        story.append(Paragraph("TRANSCRIÇÃO COM HORÁRIO", title))

        for rec in self.records:
            line = f"[{fmt_time(rec['start'])} - {fmt_time(rec['end'])}] {rec['text']}"
            story.append(Paragraph(escape(line), small))

        doc.build(story)
        return path

    def open_pdf(self):
        pdf = self.last_pdf
        if not pdf and self.current_audio:
            candidate = self.current_audio.with_name(
                self.current_audio.stem + "_AFIRMACOES_TRANSCRITAS.pdf"
            )
            if candidate.exists():
                pdf = candidate

        if not pdf:
            messagebox.showinfo("PDF", "O PDF ainda não foi gerado.")
            return

        try:
            os.startfile(str(pdf))
        except Exception as e:
            messagebox.showerror("PDF", str(e))

if __name__ == "__main__":
    App().mainloop()
