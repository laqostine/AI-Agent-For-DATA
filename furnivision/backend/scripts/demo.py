#!/usr/bin/env python3
"""FurniVision V5 — Interactive Demo Script.

Walks through the full human-in-the-loop pipeline:
  1. Create project & upload PPTX
  2. Wait for AI extraction (Agent 0)
  3. Review extracted rooms & products
  4. Approve extraction → trigger image generation
  5. Review generated images
  6. Approve images → trigger video generation
  7. Compile final walkthrough video

Usage:
    python scripts/demo.py [--pptx PATH] [--skip-wait]

Requires: backend running on localhost:8000, frontend on localhost:5173
"""

import argparse
import json
import os
import sys
import time
import webbrowser
from pathlib import Path

import requests

API = "http://localhost:8000/api/v1/v5"
FRONTEND = "http://localhost:5173"

# Default PPTX path
DEFAULT_PPTX = "/tmp/furnivision/storage/projects/5e1481dc-f7a/spec/FORTHING SHOWROOM.pptx"

BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def log(msg, color=BLUE):
    print(f"{color}{BOLD}▶{RESET} {msg}")


def success(msg):
    print(f"{GREEN}✓{RESET} {msg}")


def wait_input(msg="Press Enter to continue..."):
    input(f"\n{YELLOW}{msg}{RESET}")
    print()


def check_health():
    try:
        r = requests.get("http://localhost:8000/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def check_frontend():
    try:
        r = requests.get(FRONTEND, timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="FurniVision V5 Demo")
    parser.add_argument("--pptx", default=DEFAULT_PPTX, help="Path to PPTX spec file")
    parser.add_argument("--skip-wait", action="store_true", help="Don't wait for user input between steps")
    args = parser.parse_args()

    pptx_path = args.pptx
    auto = args.skip_wait

    print()
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}   FurniVision V5 — Human-in-the-Loop Demo{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print()
    print("This demo walks through the full pipeline:")
    print("  PPTX Upload → AI Extraction → Review → Image Gen → Video")
    print()

    # Pre-flight checks
    log("Checking backend...")
    if not check_health():
        print(f"{RED}✗ Backend not running on localhost:8000{RESET}")
        print("  Start it with: cd backend && ./venv/bin/python -m uvicorn main:app --port 8000")
        sys.exit(1)
    success("Backend healthy")

    log("Checking frontend...")
    if not check_frontend():
        print(f"{YELLOW}⚠ Frontend not running on localhost:5173 (optional for API demo){RESET}")
    else:
        success("Frontend running")

    if not Path(pptx_path).exists():
        print(f"{RED}✗ PPTX not found: {pptx_path}{RESET}")
        print("  Use --pptx PATH to specify the file")
        sys.exit(1)
    success(f"PPTX: {Path(pptx_path).name} ({Path(pptx_path).stat().st_size // 1024 // 1024}MB)")

    print()
    print(f"{BOLD}─── STEP 1: Create Project & Upload PPTX ───{RESET}")
    print()

    # Create project
    log("Creating V5 project...")
    r = requests.post(f"{API}/projects", params={"name": "Forthing Showroom Demo"})
    r.raise_for_status()
    project_id = r.json()["project_id"]
    success(f"Project created: {project_id}")

    # Upload PPTX
    log(f"Uploading {Path(pptx_path).name}...")
    with open(pptx_path, "rb") as f:
        r = requests.post(
            f"{API}/projects/{project_id}/upload-spec",
            files={"file": (Path(pptx_path).name, f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        )
    r.raise_for_status()
    success("PPTX uploaded, extraction started")

    # Open browser
    url = f"{FRONTEND}/extraction-review/{project_id}"
    log(f"Opening browser: {url}")
    webbrowser.open(url)

    print()
    print(f"{BOLD}─── STEP 2: Wait for AI Extraction (Agent 0) ───{RESET}")
    print()
    log("Agent 0 is analyzing 64 slides with Gemini...")
    log("This takes ~60 seconds (15 images sent to Gemini 2.5 Pro)")
    print()

    # Poll until extraction completes
    start = time.time()
    while True:
        r = requests.get(f"{API}/projects/{project_id}")
        data = r.json()
        status = data["status"]
        rooms = len(data.get("v5_rooms", []))
        elapsed = int(time.time() - start)

        if status == "reviewing_extraction":
            print(f"\r{GREEN}✓ Extraction complete in {elapsed}s — {rooms} rooms found{RESET}        ")
            break
        elif status == "failed":
            print(f"\r{RED}✗ Extraction failed after {elapsed}s{RESET}        ")
            sys.exit(1)
        else:
            print(f"\r  ⏳ [{elapsed}s] Status: {status}, rooms: {rooms}...", end="", flush=True)
            time.sleep(3)

    # Show extraction results
    print()
    r = requests.get(f"{API}/projects/{project_id}/extraction")
    extraction = r.json()
    print(f"  📋 {extraction['total_products']} products across {len(extraction['rooms'])} rooms:")
    print(f"  📐 {len(extraction['floor_plans'])} floor plans")
    print()
    for room in extraction["rooms"]:
        products = room.get("products", [])
        floor = room.get("floor", "?")
        print(f"    🏠 {room['label']} ({floor}) — {len(products)} products")
        for p in products[:3]:
            dims = p.get("dimensions") or ""
            print(f"       • {p['name']} {dims}")
        if len(products) > 3:
            print(f"       ... and {len(products) - 3} more")
    print()

    if not auto:
        wait_input("Review the extraction in the browser, then press Enter to approve...")

    print(f"{BOLD}─── STEP 3: Approve Extraction → Generate Images ───{RESET}")
    print()

    log("Approving extraction (triggers Imagen 4 + Gemini Flash Image)...")
    r = requests.post(f"{API}/projects/{project_id}/approve-extraction")
    r.raise_for_status()
    resp = r.json()
    success(f"Approved {resp['rooms_count']} rooms, image generation started")

    # Open image review page
    url = f"{FRONTEND}/image-review/{project_id}"
    log(f"Opening browser: {url}")
    webbrowser.open(url)

    print()
    print("  Image generation pipeline per room:")
    print("    1. Imagen 4 → 16:9 base render (1536×864)")
    print("    2. Gemini Flash Image × 3 parallel refinements with product refs")
    print("    3. Gemini picks best-of-3")
    print()
    print(f"  ⏱️  ~30s per room × {resp['rooms_count']} rooms")
    print(f"  💰 ~$0.15 per room (Imagen + Gemini)")
    print()

    if not auto:
        wait_input("Image generation is running in background. Press Enter to check status...")

    # Poll image generation
    log("Checking image generation progress...")
    start = time.time()
    while True:
        r = requests.get(f"{API}/projects/{project_id}")
        data = r.json()
        status = data["status"]
        rooms = data.get("v5_rooms", [])
        ready = sum(1 for r in rooms if r["status"] in ("image_ready", "image_approved"))
        total = len(rooms)
        elapsed = int(time.time() - start)

        if status == "reviewing_images" or ready == total:
            print(f"\r{GREEN}✓ All {total} room images generated in {elapsed}s{RESET}        ")
            break
        elif status == "failed":
            print(f"\r{RED}✗ Image generation failed{RESET}        ")
            break
        else:
            print(f"\r  ⏳ [{elapsed}s] {ready}/{total} rooms ready...", end="", flush=True)
            time.sleep(5)

    print()

    # Show generated images
    for room in data.get("v5_rooms", []):
        imgs = room.get("generated_images", [])
        if imgs:
            latest = imgs[-1]
            print(f"    🖼️  {room['label']}: v{latest['version']} ({latest['type']})")

    print()
    print(f"{BOLD}─── STEP 4: Review & Approve Images ───{RESET}")
    print()
    print("  In the browser you can:")
    print("    • Compare AI renders vs product reference images")
    print("    • Give text feedback → AI re-edits the specific issue")
    print("    • Regenerate from scratch")
    print("    • Approve each room ✓")
    print()

    if not auto:
        wait_input("Approve rooms in the browser (or press Enter to auto-approve all)...")

    # Auto-approve all rooms
    log("Auto-approving all room images...")
    for room in data.get("v5_rooms", []):
        if room["status"] == "image_ready":
            r = requests.post(f"{API}/projects/{project_id}/rooms/{room['id']}/approve")
            if r.status_code == 200:
                success(f"  Approved: {room['label']}")

    print()
    print(f"{BOLD}─── STEP 5: Generate Videos ───{RESET}")
    print()

    log("Triggering Kling video generation (fal.ai)...")
    r = requests.post(f"{API}/projects/{project_id}/generate-videos")
    if r.status_code == 200:
        resp = r.json()
        success(f"Video generation started for {resp.get('rooms_count', '?')} rooms")
        print(f"  ⏱️  ~30s per room (Kling v2.1, 7s walkthrough)")
        print(f"  💰 ~$0.28 per room")
    else:
        print(f"{YELLOW}⚠ Video generation: {r.json().get('detail', r.status_code)}{RESET}")

    # Open video preview
    url = f"{FRONTEND}/video-preview/{project_id}"
    log(f"Opening browser: {url}")
    webbrowser.open(url)

    print()
    print(f"{BOLD}─── STEP 6: Compile Final Video ───{RESET}")
    print()
    print("  Once all room videos are ready:")
    print("    • Click 'Compile Final Video' in the browser")
    print("    • ffmpeg concatenates all rooms + logo + music → 1920×1080 MP4")
    print("    • Download the final walkthrough")
    print()

    if not auto:
        wait_input("Wait for videos, then press Enter to try compilation...")

    log("Attempting compilation...")
    r = requests.post(f"{API}/projects/{project_id}/compile")
    if r.status_code == 200:
        resp = r.json()
        success(f"Final video: {resp.get('video_path', '?')}")
        print(f"  📥 Download: {FRONTEND}/api/v1/v5/projects/{project_id}/final-video")
    else:
        print(f"{YELLOW}⚠ Compilation: {r.json().get('detail', 'not ready yet')}{RESET}")
        print("  (Videos may still be generating — try again in a minute)")

    print()
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}   Demo Complete!{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print()
    print(f"  Project ID:  {project_id}")
    print(f"  Extraction:  {FRONTEND}/extraction-review/{project_id}")
    print(f"  Images:      {FRONTEND}/image-review/{project_id}")
    print(f"  Videos:      {FRONTEND}/video-preview/{project_id}")
    print()
    print("  Cost estimate for this project:")
    print("    Extraction:  ~$0.10 (Gemini Pro)")
    print("    Images:      ~$2.00 (13 rooms × Imagen + Gemini)")
    print("    Videos:      ~$3.64 (13 rooms × Kling @ $0.28)")
    print(f"    Total:       ~$5.74")
    print()


if __name__ == "__main__":
    main()
