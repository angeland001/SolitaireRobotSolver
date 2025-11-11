#!/usr/bin/env python3
"""
Quick test to verify camera is working and can see the iPad
"""

import cv2
import sys

def test_camera(camera_index=0):
    """Simple camera test"""
    print(f"\n🎥 Testing camera {camera_index}...")
    print("Press 'q' to quit")
    print("Press 'c' to capture a frame for inspection")
    
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print(f"❌ Could not open camera {camera_index}")
        print("\nTroubleshooting:")
        print("- Check camera is connected")
        print("- Try different camera_index (0, 1, 2, etc.)")
        print("- Check camera permissions")
        return False
    
    # Get camera properties
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"✓ Camera opened successfully!")
    print(f"  Resolution: {int(width)}x{int(height)}")
    print(f"  FPS: {fps}")
    
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                print("❌ Failed to capture frame")
                break
            
            frame_count += 1
            
            # Add info overlay
            info_text = f"Frame: {frame_count} | Press 'q' to quit, 'c' to capture"
            cv2.putText(frame, info_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Draw a crosshair in center
            h, w = frame.shape[:2]
            cv2.line(frame, (w//2 - 20, h//2), (w//2 + 20, h//2), (0, 255, 0), 2)
            cv2.line(frame, (w//2, h//2 - 20), (w//2, h//2 + 20), (0, 255, 0), 2)
            
            cv2.imshow("Camera Test - Position iPad in view", frame)
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("\n✓ Test completed")
                break
            elif key == ord('c'):
                filename = f"captured_frame_{frame_count}.jpg"
                cv2.imwrite(filename, frame)
                print(f"📸 Saved frame to {filename}")
    
    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")
    finally:
        cap.release()
        cv2.destroyAllWindows()
    
    return True


if __name__ == "__main__":
    # Try camera index from command line argument, default to 0
    camera_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    test_camera(camera_idx)
