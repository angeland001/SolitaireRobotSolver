#!/usr/bin/env python3
"""
Interactive Card Marker
Manually mark and label cards to help train the detection system
"""

import cv2
import json
import numpy as np
from typing import List, Tuple, Dict

class CardMarker:
    """Interactive tool for manually labeling cards in captured images"""
    
    def __init__(self, image_path: str):
        self.image_path = image_path
        self.image = cv2.imread(image_path)
        if self.image is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        self.display_image = self.image.copy()
        self.marked_cards = []
        self.current_card = None
        self.marking = False
        
        # Card ranks and suits for labeling
        self.ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        self.suits = ['H', 'D', 'C', 'S']  # Hearts, Diamonds, Clubs, Spades
        
        print("\n" + "="*60)
        print("INTERACTIVE CARD MARKER")
        print("="*60)
        print("\nInstructions:")
        print("1. Click and drag to draw box around a card")
        print("2. Type rank (A,2-10,J,Q,K) then suit (H,D,C,S)")
        print("   Example: 'KH' for King of Hearts")
        print("3. Press ENTER to save the card")
        print("4. Press 'u' to undo last card")
        print("5. Press 's' to save all marked cards")
        print("6. Press 'q' to quit without saving")
        print("="*60 + "\n")
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for drawing boxes"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.marking = True
            self.current_card = {'x1': x, 'y1': y}
        
        elif event == cv2.EVENT_MOUSEMOVE and self.marking:
            # Show preview rectangle
            temp_image = self.display_image.copy()
            cv2.rectangle(temp_image, 
                         (self.current_card['x1'], self.current_card['y1']),
                         (x, y), (0, 255, 0), 2)
            cv2.imshow("Mark Cards", temp_image)
        
        elif event == cv2.EVENT_LBUTTONUP:
            self.marking = False
            self.current_card['x2'] = x
            self.current_card['y2'] = y
            
            # Ensure x1,y1 is top-left and x2,y2 is bottom-right
            x1 = min(self.current_card['x1'], self.current_card['x2'])
            x2 = max(self.current_card['x1'], self.current_card['x2'])
            y1 = min(self.current_card['y1'], self.current_card['y2'])
            y2 = max(self.current_card['y1'], self.current_card['y2'])
            
            self.current_card = {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
            
            # Draw the box
            cv2.rectangle(self.display_image,
                         (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.imshow("Mark Cards", self.display_image)
            
            # Prompt for label
            print(f"\n📍 Marked region: ({x1},{y1}) to ({x2},{y2})")
            print("   Enter card label (e.g., 'KH', '10D', 'AS'):")
    
    def run(self):
        """Run the interactive marking session"""
        cv2.namedWindow("Mark Cards")
        cv2.setMouseCallback("Mark Cards", self.mouse_callback)
        cv2.imshow("Mark Cards", self.display_image)
        
        label_input = ""
        
        while True:
            key = cv2.waitKey(1) & 0xFF
            
            # Handle text input for labels
            if key >= 32 and key < 127:  # Printable characters
                label_input += chr(key).upper()
                print(chr(key).upper(), end='', flush=True)
            
            elif key == 8:  # Backspace
                if label_input:
                    label_input = label_input[:-1]
                    print('\b \b', end='', flush=True)
            
            elif key == 13:  # Enter
                if self.current_card and label_input:
                    self._save_current_card(label_input)
                    label_input = ""
                    self.current_card = None
            
            elif key == ord('u'):  # Undo
                self._undo_last_card()
            
            elif key == ord('s'):  # Save
                self._save_to_file()
                break
            
            elif key == ord('q'):  # Quit
                print("\n❌ Quit without saving")
                break
        
        cv2.destroyAllWindows()
    
    def _save_current_card(self, label: str):
        """Save the currently marked card"""
        if not self._validate_label(label):
            print(f"\n❌ Invalid label: {label}")
            print("   Format: <rank><suit>, e.g., 'KH', '10D', 'AS'")
            return
        
        # Parse label
        if len(label) == 2:
            rank, suit = label[0], label[1]
        elif len(label) == 3 and label[:2] == '10':
            rank, suit = '10', label[2]
        else:
            print(f"\n❌ Could not parse label: {label}")
            return
        
        # Convert suit code to full name
        suit_names = {'H': 'hearts', 'D': 'diamonds', 'C': 'clubs', 'S': 'spades'}
        suit_full = suit_names.get(suit, suit)
        
        card_data = {
            'rank': rank,
            'suit': suit_full,
            'bbox': [
                self.current_card['x1'],
                self.current_card['y1'],
                self.current_card['x2'] - self.current_card['x1'],
                self.current_card['y2'] - self.current_card['y1']
            ],
            'center': [
                (self.current_card['x1'] + self.current_card['x2']) // 2,
                (self.current_card['y1'] + self.current_card['y2']) // 2
            ]
        }
        
        self.marked_cards.append(card_data)
        
        # Draw on display
        x1, y1 = self.current_card['x1'], self.current_card['y1']
        x2, y2 = self.current_card['x2'], self.current_card['y2']
        cv2.rectangle(self.display_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(self.display_image, label, (x1, y1-10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("Mark Cards", self.display_image)
        
        print(f"\n✓ Saved card: {rank} of {suit_full}")
        print(f"  Total cards marked: {len(self.marked_cards)}")
    
    def _validate_label(self, label: str) -> bool:
        """Validate card label format"""
        if len(label) < 2 or len(label) > 3:
            return False
        
        # Check rank
        if len(label) == 2:
            rank = label[0]
            suit = label[1]
        elif len(label) == 3:
            rank = label[:2]
            suit = label[2]
        else:
            return False
        
        return rank in self.ranks and suit in self.suits
    
    def _undo_last_card(self):
        """Remove the last marked card"""
        if self.marked_cards:
            removed = self.marked_cards.pop()
            print(f"\n↩️  Undid: {removed['rank']} of {removed['suit']}")
            
            # Redraw display
            self.display_image = self.image.copy()
            for card in self.marked_cards:
                x, y, w, h = card['bbox']
                label = f"{card['rank']}{card['suit'][0].upper()}"
                cv2.rectangle(self.display_image, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(self.display_image, label, (x, y-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.imshow("Mark Cards", self.display_image)
        else:
            print("\n⚠️  No cards to undo")
    
    def _save_to_file(self):
        """Save marked cards to JSON file"""
        if not self.marked_cards:
            print("\n⚠️  No cards marked, nothing to save")
            return
        
        output_file = self.image_path.replace('.jpg', '_marked.json').replace('.png', '_marked.json')
        
        data = {
            'image_file': self.image_path,
            'image_size': {
                'width': self.image.shape[1],
                'height': self.image.shape[0]
            },
            'cards': self.marked_cards
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n💾 Saved {len(self.marked_cards)} cards to: {output_file}")


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python card_marker.py <image_file>")
        print("\nExample:")
        print("  python card_marker.py captured_frame_1.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    try:
        marker = CardMarker(image_path)
        marker.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
