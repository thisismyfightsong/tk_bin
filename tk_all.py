#!/usr/bin/env python3

import re
import os
import sys
import base64
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from io import BytesIO

from PIL import Image, ImageFile, UnidentifiedImageError, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from openai import OpenAI
import cv2
import time
from picamera2 import Picamera2
from datetime import datetime

# Ensure stdout/stderr use UTF‑8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Allow PIL to load truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Initialize OpenAI client (replace with your key)
client = OpenAI(api_key="")


def open_file(file_path, max_width=800, max_height=600):
    try:
        with Image.open(file_path) as img:
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.thumbnail((max_width, max_height))
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            buf.seek(0)
            return "data:image/jpeg;base64," + base64.b64encode(buf.read()).decode("utf-8")
    except (OSError, UnidentifiedImageError) as e:
        print(f"[ERROR] Skipping corrupt image {file_path}: {e}")
        return None


def open_images_base64(folder):
    imgs = []
    for fn in os.listdir(folder):
        path = os.path.join(folder, fn)
        if os.path.isfile(path) and fn.lower().endswith(('.jpg','jpeg','png','bmp','gif')):
            b64 = open_file(path)
            if b64:
                imgs.append(b64)
    print(f"[INFO] Loaded {len(imgs)} images from {folder}")
    return imgs


def analyze_image(image_b64, prompt):
    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps([
                    {"type": "text",      "text": "Classify this image"},
                    {"type": "image_url", "image_url": {"url": image_b64}}
                ])},
            ],
            max_tokens=2000,
        )
        text = resp.choices[0].message.content or ""
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            raise ValueError("no JSON object in response")
        return json.loads(m.group(0))
    except Exception as e:
        print(f"[WARN] analyze_image skipped: {e}")
        return None


class Redirector:
    def __init__(self, widget):
        self.widget = widget
    def write(self, msg):
        self.widget.after(0, self._append, msg)
    def _append(self, msg):
        self.widget.configure(state='normal')
        self.widget.insert('end', msg)
        self.widget.configure(state='disabled')
        self.widget.yview('end')
    def flush(self):
        pass


class FoodWasteAnalyzer:
    def __init__(self, root):
        self.root = root
        root.title("SmartBin AI - Food Waste Analysis")
        style = ttk.Style()
        style.theme_use("clam")

        # ? override the default ttk Frame so your whole window is #edf6ee
        style.configure('TFrame', background='#edf6ee')
        style.configure('TLabel', foreground='#1b9c85', background='#edf6ee')

        # ? define a new button style
        style.configure(
            'Custom.TButton',
            background='#edf6ee',     # normal background
            foreground='#004d40',     # text colour
            borderwidth=1,
            focusthickness=3,
            focuscolor='none'
        )
        # ? tweak how it looks when hovered/pressed
        style.configure(
            'BlackBorder.TButton',
            background='#edf6ee',    # your normal bg
            foreground='#004d40',    # your normal fg
            bordercolor='#000000',   # the actual border color
            darkcolor='#000000',     # darker edge
            lightcolor='#000000',    # lighter edge
            borderwidth=0.5,           # how thick the border is
            relief='solid'           # give it a solid?line look
        )
        
        style.configure(
          'My.TCombobox',            # the name of your new style
          fieldbackground='#edf6ee',  # the ?editable? part of the widget
          background='#edf6ee',       # the panel & arrow background
          foreground='#004d40',       # the text colour
          arrowcolor  ='#004d40'      # (clam only) the little arrow
        )
        
        style.configure(
            'Refresh.TButton',
            padding=(2,2),
            bordercolor='black',
            background='#edf6ee',
            foreground='#004d40',
        )
        
        style.map(
            'My.TCombobox',
            fieldbackground=[('readonly', '#edf6ee')],
            background    =[('readonly', '#edf6ee')]
        )
                
        # Main frame
        frame = ttk.Frame(root, padding=20)
        frame.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(5, weight=1)  # allow canvas to expand

        # Title
        ttk.Label(frame, text="SmartBin AI - Food Waste Analysis", font=('Arial',20,'bold'), style='Title.TLabel').grid(row=0, column=0, pady=(0,20))

        wf = ttk.Frame(frame); wf.grid(row=1, column=0, pady=(0,20))
        wf.columnconfigure(1, weight=1)

        ttk.Label(wf, text="Select Week:", font=('Arial',12))\
            .grid(row=0, column=0, padx=(0,10))

        self.week_var = tk.StringVar()
        self.week_dd = ttk.Combobox(
            wf, textvariable=self.week_var,
            state="readonly", width=25,
            style='My.TCombobox'
        )
        self.week_dd.grid(row=0, column=1, sticky="ew")

        refresh_btn = ttk.Button(
            wf,
            text="↻",
            width=3,
            command=self.populate_weeks,
            style='Refresh.TButton'
        )
        refresh_btn.grid(row=0, column=2, padx=(5,0))

        self.populate_weeks()

        # Buttons
        bf = ttk.Frame(frame); bf.grid(row=2, column=0, pady=(0,20))
        for i in range(4): bf.columnconfigure(i, weight=1)
        self.capture_btn = ttk.Button(bf, text="Capture Images", command=self.capture_images, style='BlackBorder.TButton')
        self.capture_btn.grid(row=0, column=0, padx=5, sticky="ew")
        self.stop_btn    = ttk.Button(bf, text="Stop Capture",  command=self.stop_capture, style='BlackBorder.TButton')
        self.stop_btn.grid(row=0, column=1, padx=5, sticky="ew")
        self.analyze_btn = ttk.Button(bf, text="Analyse via JSON", command=self.start_analysis, style='BlackBorder.TButton')
        self.analyze_btn.grid(row=0, column=2, padx=5, sticky="ew")
        self.close_btn   = ttk.Button(bf, text="Close App",     command=root.destroy, style='BlackBorder.TButton')
        self.close_btn.grid(row=0, column=3, padx=5, sticky="ew")

        # — White “terminal” box for all print() output —
        self.log = ScrolledText(frame, state='disabled', height=10, bg='white')
        self.log.grid(row=3, column=0, sticky="nsew", pady=(0,20))
        sys.stdout = sys.stderr = Redirector(self.log)

        # Status label
        self.status = ttk.Label(frame, text="Ready", font=('Arial',12))
        self.status.grid(row=4, column=0, pady=(0,10))

        # Canvas placeholder
        self.canvas_frame = ttk.Frame(frame)
        self.canvas_frame.grid(row=5, column=0, sticky="nsew")
        self.canvas = None

        # Internal flags
        self.capturing = False
        self.capture_thread = None
        self.analysis_thread = None


    def populate_weeks(self):
        if os.path.isdir('Images'):
            weeks = sorted(d for d in os.listdir('Images') 
                           if os.path.isdir(os.path.join('Images',d)))
            self.week_dd['values'] = weeks
            if weeks: self.week_dd.set(weeks[0])
        else:
            self.week_dd.set("Images folder missing")


    def capture_images(self):
        if self.capturing: 
            return
        self.capturing = True

        def loop():
            cam = Picamera2()
            cfg = cam.create_still_configuration()
            cfg["main"]["size"] = (2592,1944)
            cam.configure(cfg); cam.start()

            folder = f"Images/{datetime.now():%Y%m%d_%H%M%S}"
            os.makedirs(folder, exist_ok=True)
            num = 1

            while self.capturing:
                frame = cam.capture_array()
                roi   = frame[527:527+637, 760:760+740]
                gray  = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                _,th  = cv2.threshold(gray, 240,255, cv2.THRESH_BINARY)
                if np.any((th>=225)&(th<=255)):
                    fn = f"{folder}/img_{num}.jpg"
                    cam.capture_file(fn)
                    print(f"[{datetime.now().isoformat()}] Captured {fn}")
                    num += 1
                else:
                    print(f"[{datetime.now().isoformat()}] No plate")
                time.sleep(0.25)

            cam.stop(); cam.close()

        self.capture_thread = threading.Thread(target=loop, daemon=True)
        self.capture_thread.start()


    def stop_capture(self):
        self.capturing = False
        print(f"[{datetime.now().isoformat()}] Capture stopped")


    def start_analysis(self):
        self.analyze_btn.config(state='disabled')
        self.analysis_thread = threading.Thread(target=self.do_analysis, daemon=True)
        self.analysis_thread.start()


    def do_analysis(self):
        week = self.week_var.get()
        if not week or not os.path.isdir(os.path.join('Images',week)):
            messagebox.showerror("Error","Please select a valid week")
            self.analyze_btn.config(state='normal')
            return

        # load prompt
        try:
            with open('prompt.txt','r',encoding='utf-8') as f:
                PROMPT = f.read()
        except FileNotFoundError:
            messagebox.showerror("Error","prompt.txt missing")
            self.analyze_btn.config(state='normal')
            return

        # gather images
        path = os.path.join('Images',week)
        imgs = open_images_base64(path)
        if not imgs:
            messagebox.showerror("Error","No images in folder")
            self.analyze_btn.config(state='normal')
            return

        # analyze
        results = []
        for i,img in enumerate(imgs,1):
            self.status.config(text=f"Processing {i}/{len(imgs)}…")
            self.root.update()
            res = analyze_image(img, PROMPT)
            if res:
                results.append(res)

        # write JSON
        ts = datetime.now().strftime("%d-%H-%M-%Y")
        outname = f"JSON/JSON_{week}_{ts}.json"
        os.makedirs("JSON", exist_ok=True)
        with open(outname,'w',encoding='utf-8') as f:
            json.dump({"analysis_results":results}, f, indent=4)
        print(f"[INFO] Analysis complete – saved to {outname}")

        # no results?
        if not results:
            messagebox.showwarning("No data","No plates found in any image")
            self.analyze_btn.config(state='normal')
            return

        # aggregate & plot
        totals = {}
        for r in results:
            for plate in r.get("plates",[]):
                for itm in plate:
                    name = itm.get("name","").strip()
                    qty  = float(itm.get("quantity",0))
                    if name.upper()=="EMPTY": continue
                    totals[name] = totals.get(name,0)+qty

        total = sum(totals.values())
        pct   = {k:(v/total)*100 for k,v in totals.items()}
        most  = max(pct, key=pct.get)

        # draw bar chart
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
            
            
        fig, ax = plt.subplots(figsize=(6,4), dpi=100, constrained_layout=True)
        
        fig, ax = plt.subplots(
            figsize=(6,4),
            dpi=100,
            constrained_layout=True,
            facecolor='#edf6ee'      # ? sets the figure background
        )
        ax.set_facecolor('#edf6ee')  # ? sets the plotting area (axes) background

        bars = ax.bar(pct.keys(), pct.values(),
                      color=[ 'red' if f==most else 'blue' for f in pct ])
        ax.set_title(f"Waste % by Type ({week})")
        ax.set_ylabel("% waste")
        plt.setp(ax.get_xticklabels(), rotation=30, ha='right')
        for b,label in zip(bars,pct):
            ax.text(b.get_x()+b.get_width()/2, b.get_height(),
                    f"{pct[label]:.1f}%", ha='center', va='bottom')

        self.canvas = FigureCanvasTkAgg(fig, self.canvas_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        self.status.config(text=f"Done – most wasted: {most} ({pct[most]:.1f}%)")
        self.analyze_btn.config(state='normal')


if __name__ == "__main__":
    root = tk.Tk()
    FoodWasteAnalyzer(root)
    root.mainloop()




