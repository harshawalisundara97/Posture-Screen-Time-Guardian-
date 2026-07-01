import time
import cv2
from posture_guardian.posture_engine import PoseEngine
from posture_guardian.posture_engine import landmarks_to_metrics

cap = cv2.VideoCapture(0)
engine = PoseEngine()

print("Sit in view of the webcam. Printing metrics for 5 seconds...")
start = time.time()
while time.time() - start < 5:
    ok, frame = cap.read()
    if not ok:
        print("Failed to read from webcam")
        break
    landmarks = engine.process_frame(frame)
    if landmarks is None:
        print("no person detected")
        continue
    metrics = landmarks_to_metrics(landmarks)
    print(f"neck_angle={metrics.neck_angle:.1f} shoulder_tilt={metrics.shoulder_tilt:.3f} forward_lean={metrics.forward_lean:.3f}")

cap.release()
engine.close()
