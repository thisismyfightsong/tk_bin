# SmartBin AI

SmartBin AI is a module that reduces food waste using artificial intelligence. It works by placing a camera setup above a school's cafeteria or kitchen bin, where food waste is usually thrown away by students. When a plate is detected, it captures an image and sends it through a CNN model that identifies the type of food and estimates the amount of waste.

Every month, it automatically generates a report based on the collected data. This report is sent to the food provider with suggestions, like adjusting portion sizes for meals that are often left unfinished.

## How it works

1. The module waits for a plate to appear in its field of view.
2. Once a plate is detected, it takes a photo.
3. The photo is passed to an AI model that:
   - Detects food items.
   - Estimates the percentage of food left.
4. The data is logged and included in a monthly report.

## Hardware

- Raspberry Pi 4 or 5 (depending on model performance)
- Camera module (set up above the bin)
- Optional: enclosure for weather or mess protection

## Software

- Python (main language)
- OpenCV (for image processing)
- TensorFlow or PyTorch (used to train the CNN)
- Optionally connected to Google Sheets or a dashboard to show live data

## Use case

This was made mainly for school cafeterias, but it can be used anywhere food is served in bulk — like buffets, hostels, or events. The goal is to give kitchens real data about what people are wasting, so they can make smarter decisions on what and how much to serve.

## Folder structure

- `capture/` – handles camera feed and image saving
- `model/` – contains the trained CNN model
- `reporting/` – generates monthly insights
- `scripts/` – extra tools for calibration or manual testing

## Setup

1. Clone the repo to your Raspberry Pi.
2. Make sure your environment has Python and the required libraries (`pip install -r requirements.txt`).
3. Run the main script:  
   `python3 run.py`
4. Position the module so it clearly sees the bin and plate area.

## Notes

- This is still being improved based on real-world testing.
- The accuracy improves as more training data is added from different schools or food types.
- One limitation is lighting – it works best in areas with consistent light.
