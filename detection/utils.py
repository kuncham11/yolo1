import time
import math
from datetime import datetime

# Safe import for OpenCV and NumPy
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    CV2_AVAILABLE = False

def draw_corner_rect(img, pt1, pt2, color, thickness=2, d=12):
    """
    Draws modern sci-fi / security camera HUD corner brackets on bounding boxes.
    """
    if not CV2_AVAILABLE or img is None:
        return img

    x1, y1 = int(pt1[0]), int(pt1[1])
    x2, y2 = int(pt2[0]), int(pt2[1])

    # Ensure coordinates are within image boundaries
    h, w = img.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w - 1, x2), min(h - 1, y2)

    # Base thin rectangle
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 1)

    # Top-Left corner
    cv2.line(img, (x1, y1), (x1 + d, y1), color, thickness)
    cv2.line(img, (x1, y1), (x1, y1 + d), color, thickness)

    # Top-Right corner
    cv2.line(img, (x2, y1), (x2 - d, y1), color, thickness)
    cv2.line(img, (x2, y1), (x2, y1 + d), color, thickness)

    # Bottom-Left corner
    cv2.line(img, (x1, y2), (x1 + d, y2), color, thickness)
    cv2.line(img, (x1, y2), (x1, y2 - d), color, thickness)

    # Bottom-Right corner
    cv2.line(img, (x2, y2), (x2 - d, y2), color, thickness)
    cv2.line(img, (x2, y2), (x2, y2 - d), color, thickness)

    return img

def draw_person_boxes(frame, detections, weapons=None, accidents=None, camera_id="CCTV-01", fps=30.0, show_hud=True):
    """
    Overlays exact person identification, real-time person count, motion detection status,
    trajectory kinematics, weapons warnings, accident / fall alerts, and surveillance HUD telemetry.
    Does NOT show arbitrary/default person track IDs; shows real-time person count and motion state.
    """
    if not CV2_AVAILABLE or frame is None:
        return frame

    h, w = frame.shape[:2]
    total_persons = len(detections)

    # Draw individual person bounding boxes & real-time count / motion metadata
    for idx, det in enumerate(detections):
        bbox = det.get("bbox", [0, 0, 0, 0])
        conf = det.get("confidence", 0.0)
        vel = det.get("velocity", 0.0)
        direction = det.get("direction", "Stationary")
        x1, y1, x2, y2 = bbox

        # Motion detection status & color coding
        if vel > 15.0:
            box_color = (0, 140, 255) # Warning Amber/Orange (BGR)
            motion_label = f"MOTION DETECTED: RUNNING | {vel:.1f} px/f"
            motion_tag_color = (0, 140, 255)
        elif vel > 1.5:
            box_color = (0, 220, 130) # High-visibility Neon Green (BGR)
            motion_label = f"MOTION DETECTED: {direction} | {vel:.1f} px/f"
            motion_tag_color = (0, 220, 130)
        else:
            box_color = (212, 182, 6) # Neon Cyan-Blue (BGR)
            motion_label = "MOTION: STATIONARY (IDLE)"
            motion_tag_color = (180, 180, 180)

        draw_corner_rect(frame, (x1, y1), (x2, y2), box_color, thickness=2, d=10)

        # Primary label: Exact person identification and real-time count (e.g. PERSON 1 OF 3 [94%])
        # NEVER show default person IDs like "Person ID #123"
        person_num = idx + 1
        label = f"PERSON {person_num} OF {total_persons} [{int(conf * 100)}%]"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.42
        font_thick = 1
        (lw, lh), _ = cv2.getTextSize(label, font, font_scale, font_thick)

        # Background tag above box
        tag_y1 = max(0, int(y1) - lh - 8)
        tag_y2 = max(lh + 8, int(y1))
        cv2.rectangle(frame, (int(x1), tag_y1), (int(x1) + lw + 10, tag_y2), (10, 15, 26), -1)
        cv2.rectangle(frame, (int(x1), tag_y1), (int(x1) + lw + 10, tag_y2), box_color, 1)
        cv2.putText(frame, label, (int(x1) + 4, tag_y2 - 5), font, font_scale, (255, 255, 255), font_thick, cv2.LINE_AA)

        # Secondary tag below box for kinematics & Motion Detection
        (kw, kh), _ = cv2.getTextSize(motion_label, font, 0.35, 1)
        kin_y1 = min(h - 1, int(y2))
        kin_y2 = min(h - 1, int(y2) + kh + 6)
        cv2.rectangle(frame, (int(x1), kin_y1), (int(x1) + kw + 8, kin_y2), (10, 15, 26), -1)
        cv2.rectangle(frame, (int(x1), kin_y1), (int(x1) + kw + 8, kin_y2), (31, 41, 61), 1)
        cv2.putText(frame, motion_label, (int(x1) + 4, kin_y2 - 3), font, 0.35, motion_tag_color, 1, cv2.LINE_AA)

        # Centroid target dot
        cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
        cv2.circle(frame, (cx, cy), 3, (0, 255, 0), -1)

    # Draw Weapon Detections (Urgent Red Warning Overlay)
    if weapons:
        for wpn in weapons:
            wb = wpn.get("bbox", [0, 0, 0, 0])
            wcls = wpn.get("class", "WEAPON").upper()
            wconf = wpn.get("confidence", 0.9)
            wx1, wy1, wx2, wy2 = wb

            # Red warning box
            red_color = (0, 0, 255) # BGR Red
            draw_corner_rect(frame, (wx1, wy1), (wx2, wy2), red_color, thickness=3, d=12)

            wpn_label = f"ALERT: {wcls} [{int(wconf * 100)}%]"
            (wlw, wlh), _ = cv2.getTextSize(wpn_label, font, 0.45, 1)
            wtag_y1 = max(0, int(wy1) - wlh - 8)
            wtag_y2 = max(wlh + 8, int(wy1))

            cv2.rectangle(frame, (int(wx1), wtag_y1), (int(wx1) + wlw + 12, wtag_y2), (0, 0, 200), -1)
            cv2.rectangle(frame, (int(wx1), wtag_y1), (int(wx1) + wlw + 12, wtag_y2), (255, 255, 255), 1)
            cv2.putText(frame, wpn_label, (int(wx1) + 6, wtag_y2 - 5), font, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    # Draw Accident Detections (Urgent Medical Warning Overlay)
    if accidents:
        for acc in accidents:
            ab = acc.get("bbox", [0, 0, 0, 0])
            acls = acc.get("label", "ACCIDENT: PERSON FALLEN").upper()
            aconf = acc.get("confidence", 0.85)
            ax1, ay1, ax2, ay2 = ab

            # Bright Amber / Safety Orange (BGR)
            orange_color = (0, 120, 255)
            draw_corner_rect(frame, (ax1, ay1), (ax2, ay2), orange_color, thickness=3, d=12)

            acc_label = f"EMERGENCY: {acls} [{int(aconf * 100)}%]"
            (alw, alh), _ = cv2.getTextSize(acc_label, font, 0.42, 1)
            atag_y1 = max(0, int(ay1) - alh - 8)
            atag_y2 = max(alh + 8, int(ay1))

            cv2.rectangle(frame, (int(ax1), atag_y1), (int(ax1) + alw + 12, atag_y2), (0, 80, 220), -1)
            cv2.rectangle(frame, (int(ax1), atag_y1), (int(ax1) + alw + 12, atag_y2), (255, 255, 255), 1)
            cv2.putText(frame, acc_label, (int(ax1) + 6, atag_y2 - 5), font, 0.42, (255, 255, 255), 1, cv2.LINE_AA)

    # Flashing Emergency Alert Banner when high-risk threats detected
    if weapons or accidents:
        banner_h = 32
        banner_y1 = 36 if show_hud else 0
        banner_y2 = banner_y1 + banner_h
        # Alternating flashing red/dark-red alert strip
        bg_col = (0, 0, 180) if int(time.time() * 2) % 2 == 0 else (0, 0, 240)
        cv2.rectangle(frame, (0, banner_y1), (w, banner_y2), bg_col, -1)
        cv2.line(frame, (0, banner_y2), (w, banner_y2), (255, 255, 255), 1)

        banner_text = "EMERGENCY ALERT: CONTACT POLICE (911) | AMBULANCE (108) | TV CHANNEL BROADCAST"
        (bw, bh), _ = cv2.getTextSize(banner_text, font, 0.42, 1)
        bx = max(10, (w - bw) // 2)
        cv2.putText(frame, banner_text, (bx, banner_y2 - 10), font, 0.42, (255, 255, 255), 1, cv2.LINE_AA)

    if show_hud:
        # Top HUD Bar Overlay
        cv2.rectangle(frame, (0, 0), (w, 36), (10, 15, 26), -1)
        cv2.line(frame, (0, 36), (w, 36), (31, 41, 61), 1)

        # REC indicator
        cv2.circle(frame, (18, 18), 5, (0, 0, 255), -1)
        cv2.putText(frame, "LIVE REC", (28, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        # Camera ID & Person Detection & Motion Tracking Engine info
        hud_info = f"{camera_id} | PERSON IDENTIFICATION & MOTION DETECTION | FPS: {fps:.1f}"
        cv2.putText(frame, hud_info, (110, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (200, 200, 200), 1, cv2.LINE_AA)

        # Timestamp
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        (tw, _), _ = cv2.getTextSize(ts, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        cv2.putText(frame, ts, (w - tw - 14, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (6, 182, 212), 1, cv2.LINE_AA)

        # Bottom Count Pill: Real-Time Person Count & Motion Detection
        people_count = len(detections)
        motion_count = sum(1 for d in detections if d.get("velocity", 0.0) > 1.5)
        density_label = "NORMAL" if people_count <= 10 else ("MODERATE" if people_count <= 20 else "HIGH")
        motion_str = f"{motion_count} MOVING" if motion_count > 0 else "NONE"
        count_str = f"REAL-TIME PERSON COUNT: {people_count} | MOTION DETECTED: {motion_str} | DENSITY: {density_label}"

        (cw, ch), _ = cv2.getTextSize(count_str, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
        pill_w = max(340, cw + 20)
        cv2.rectangle(frame, (10, h - 34), (10 + pill_w, h - 10), (10, 15, 26), -1)
        cv2.rectangle(frame, (10, h - 34), (10 + pill_w, h - 10), (6, 182, 212), 1)
        cv2.putText(frame, count_str, (18, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA)

    return frame

def create_camera_standby_frame(camera_id="CCTV-01", camera_name="Entrance", width=640, height=360, tick=0, draw_overlay=True):
    """
    Generates a pitch-black CCTV camera standby / inactive screen when the camera is not turned on.
    NO fake simulated persons, NO silhouettes, NO fake bounding boxes.
    Always returns exact 0 detections ([]).
    """
    if not CV2_AVAILABLE or cv2 is None:
        return None, []

    # Pure black surveillance standby screen
    frame = np.zeros((height, width, 3), dtype=np.uint8)

    # Center Standby / Inactive Notification
    center_y = height // 2
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    title_text = "CAMERA STANDBY // INACTIVE"
    (tw, th), _ = cv2.getTextSize(title_text, font, 0.58, 2)
    tx = max(10, (width - tw) // 2)
    cv2.putText(frame, title_text, (tx, center_y - 12), font, 0.58, (80, 95, 120), 2, cv2.LINE_AA)

    sub_text = "ACTIVATE CCTV CAMERA TO START YOLO DETECTION"
    (sw, sh), _ = cv2.getTextSize(sub_text, font, 0.38, 1)
    sx = max(10, (width - sw) // 2)
    cv2.putText(frame, sub_text, (sx, center_y + 16), font, 0.38, (55, 70, 95), 1, cv2.LINE_AA)

    # Top HUD Bar Overlay
    if draw_overlay:
        cv2.rectangle(frame, (0, 0), (width, 36), (8, 10, 15), -1)
        cv2.line(frame, (0, 36), (width, 36), (20, 26, 38), 1)

        # Standby status dot (amber/gray)
        cv2.circle(frame, (18, 18), 5, (120, 120, 120), -1)
        cv2.putText(frame, "STANDBY", (28, 22), font, 0.45, (160, 160, 160), 1, cv2.LINE_AA)

        # Camera ID & Info
        hud_info = f"{camera_id} // WAITING FOR CAMERA ACTIVATION"
        cv2.putText(frame, hud_info, (110, 22), font, 0.40, (130, 140, 155), 1, cv2.LINE_AA)

        # Timestamp
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        (tsw, _), _ = cv2.getTextSize(ts, font, 0.42, 1)
        cv2.putText(frame, ts, (width - tsw - 14, 22), font, 0.42, (100, 120, 140), 1, cv2.LINE_AA)

        # Bottom Count Pill: 0 Persons (Standby)
        count_str = "REAL-TIME PERSON COUNT: 0 | MOTION: STANDBY | STATUS: CAMERA INACTIVE"
        (cw, ch), _ = cv2.getTextSize(count_str, font, 0.38, 1)
        pill_w = max(340, cw + 20)
        cv2.rectangle(frame, (10, height - 34), (10 + pill_w, height - 10), (8, 10, 15), -1)
        cv2.rectangle(frame, (10, height - 34), (10 + pill_w, height - 10), (30, 40, 55), 1)
        cv2.putText(frame, count_str, (18, height - 18), font, 0.38, (140, 150, 165), 1, cv2.LINE_AA)

    # Exact real detections: ZERO
    return frame, []

# Alias for backward compatibility
create_synthetic_feed_frame = create_camera_standby_frame
