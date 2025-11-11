#!/usr/bin/env python3
"""
Card Detection Module for iPad Solitaire Solver
Uses OpenCV to detect and identify playing cards on screen
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Card:
    """Represents a detected playing card"""
    rank: str  # '2'-'10', 'J', 'Q', 'K', 'A'
    suit: str  # 'hearts', 'diamonds', 'clubs', 'spades'
    position: Tuple[int, int]  # (x, y) center position in pixels
    bbox: Tuple[int, int, int, int]  # (x, y, width, height) bounding box
    confidence: float  # Detection confidence 0-1
    
    def __repr__(self):
        return f"{self.rank} of {self.suit} at ({self.position[0]}, {self.position[1]})"


class CardDetector:
    """Detects and identifies playing cards from camera feed"""
    
    def __init__(self, camera_index: int = 0, debug: bool = False):
        """
        Initialize card detector
        
        Args:
            camera_index: Camera device index (0 for default webcam)
            debug: If True, show debug windows with detection visualization
        """
        self.camera_index = camera_index
        self.debug = debug
        self.cap = None
        
        # Card dimensions (will be refined during detection)
        self.expected_card_ratio = 0.7  # Height/width ratio for standard playing cards
        self.min_card_area = 2000  # Minimum pixel area for a card
        self.max_card_area = 50000  # Maximum pixel area for a card
        
        # Color ranges for suit detection (HSV)
        self.red_ranges = [
            (np.array([0, 50, 50]), np.array([10, 255, 255])),      # Lower red
            (np.array([170, 50, 50]), np.array([180, 255, 255]))    # Upper red
        ]
        self.black_range = (np.array([0, 0, 0]), np.array([180, 255, 80]))
        
        print("🎴 Card Detector initialized")
    
    def start_camera(self) -> bool:
        """Initialize camera capture"""
        self.cap = cv2.VideoCapture(self.camera_index)
        
        if not self.cap.isOpened():
            print(f"❌ Failed to open camera {self.camera_index}")
            return False
        
        # Set camera properties for better quality
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        
        print(f"✓ Camera {self.camera_index} opened successfully")
        return True
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame from camera"""
        if self.cap is None or not self.cap.isOpened():
            print("❌ Camera not initialized")
            return None
        
        ret, frame = self.cap.read()
        if not ret:
            print("❌ Failed to capture frame")
            return None
        
        return frame
    
    def detect_cards(self, frame: np.ndarray) -> List[Card]:
        """
        Detect all playing cards in the frame
        
        Args:
            frame: BGR image from camera
            
        Returns:
            List of detected Card objects
        """
        if frame is None:
            return []
        
        # Preprocess image
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Adaptive thresholding to handle varying lighting
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # Find contours
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        detected_cards = []
        
        # Analyze each contour
        for contour in contours:
            card = self._analyze_contour(contour, frame, gray)
            if card:
                detected_cards.append(card)
        
        if self.debug:
            self._draw_debug_info(frame, detected_cards)
        
        print(f"🎴 Detected {len(detected_cards)} cards")
        return detected_cards
    
    def _analyze_contour(self, contour, frame: np.ndarray, 
                        gray: np.ndarray) -> Optional[Card]:
        """Analyze a contour to determine if it's a card"""
        area = cv2.contourArea(contour)
        
        # Filter by area
        if area < self.min_card_area or area > self.max_card_area:
            return None
        
        # Get bounding rectangle
        x, y, w, h = cv2.boundingRect(contour)
        
        # Check aspect ratio (cards are taller than wide)
        aspect_ratio = h / w if w > 0 else 0
        if aspect_ratio < 1.2 or aspect_ratio > 1.8:
            return None
        
        # Get card center
        center_x = x + w // 2
        center_y = y + h // 2
        
        # Extract rank and suit (simplified for now)
        rank, suit, confidence = self._identify_card(frame, x, y, w, h)
        
        return Card(
            rank=rank,
            suit=suit,
            position=(center_x, center_y),
            bbox=(x, y, w, h),
            confidence=confidence
        )
    
    def _identify_card(self, frame: np.ndarray, x: int, y: int, 
                      w: int, h: int) -> Tuple[str, str, float]:
        """
        Identify the rank and suit of a card
        
        This is a simplified version - you'll want to enhance this with
        template matching or ML-based recognition
        
        Args:
            frame: Full frame image
            x, y, w, h: Bounding box of card
            
        Returns:
            (rank, suit, confidence)
        """
        # Extract card region
        card_roi = frame[y:y+h, x:x+w]
        
        # For now, extract just the top-left corner where rank/suit typically are
        corner_h = h // 4
        corner_w = w // 3
        corner_roi = card_roi[0:corner_h, 0:corner_w]
        
        # Convert to HSV for color detection
        hsv = cv2.cvtColor(corner_roi, cv2.COLOR_BGR2HSV)
        
        # Detect suit by color
        is_red = self._detect_red(hsv)
        
        # Placeholder rank detection (you'll enhance this)
        rank = "?"
        suit = "hearts" if is_red else "spades"  # Simplified
        confidence = 0.5  # Placeholder
        
        return rank, suit, confidence
    
    def _detect_red(self, hsv: np.ndarray) -> bool:
        """Detect if the card has red suit (hearts/diamonds)"""
        mask1 = cv2.inRange(hsv, self.red_ranges[0][0], self.red_ranges[0][1])
        mask2 = cv2.inRange(hsv, self.red_ranges[1][0], self.red_ranges[1][1])
        red_mask = cv2.bitwise_or(mask1, mask2)
        
        red_pixels = cv2.countNonZero(red_mask)
        total_pixels = hsv.shape[0] * hsv.shape[1]
        
        return (red_pixels / total_pixels) > 0.05  # >5% red pixels
    
    def _draw_debug_info(self, frame: np.ndarray, cards: List[Card]):
        """Draw debug visualization on frame"""
        debug_frame = frame.copy()
        
        for card in cards:
            x, y, w, h = card.bbox
            
            # Draw bounding box
            color = (0, 255, 0) if card.confidence > 0.7 else (0, 255, 255)
            cv2.rectangle(debug_frame, (x, y), (x+w, y+h), color, 2)
            
            # Draw center point
            cv2.circle(debug_frame, card.position, 5, (255, 0, 0), -1)
            
            # Draw label
            label = f"{card.rank}{card.suit[0].upper()}"
            cv2.putText(debug_frame, label, (x, y-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        cv2.imshow("Card Detection Debug", debug_frame)
        cv2.waitKey(1)
    
    def close(self):
        """Release camera resources"""
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        print("✓ Camera closed")


# Test/demo function
def test_card_detection():
    """Test the card detection system"""
    print("\n" + "="*60)
    print("CARD DETECTION TEST")
    print("="*60)
    print("\nPress 'q' to quit, 's' to capture and analyze")
    
    detector = CardDetector(camera_index=0, debug=True)
    
    if not detector.start_camera():
        return
    
    try:
        while True:
            frame = detector.capture_frame()
            if frame is None:
                break
            
            # Show live feed
            cv2.imshow("Live Feed", frame)
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord('s'):
                print("\n📸 Analyzing frame...")
                cards = detector.detect_cards(frame)
                for card in cards:
                    print(f"  {card}")
                print()
    
    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")
    finally:
        detector.close()


if __name__ == "__main__":
    test_card_detection()
