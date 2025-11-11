import time
from plotter_controller import PenPlotter
from CoordinateMapper_Swapped import CoordinateMapper

class SmartPlotterCalibrator:
    """Enhanced calibrator that automatically detects and handles axis swapping"""
    
    def __init__(self, plotter: PenPlotter):
        self.plotter = plotter
        self.mapper = None
        self.axes_swapped = False
        self.x_inverted = False
        self.y_inverted = False
    
    def test_axis_directions(self):
        """
        Test which direction each axis moves and detect axis swapping
        Returns: (axes_swapped, x_inverted, y_inverted)
        """
        print("\n" + "="*60)
        print("STEP 1: TESTING AXIS DIRECTIONS")
        print("="*60)
        print("\nThis test determines how your plotter's axes are oriented.")
        print("Watch carefully and answer honestly about what you observe.\n")
        
        self.plotter.pen_up()
        self.plotter.move_to(50, 50)
        input("Plotter at starting position (50, 50). Press Enter...")
        
        # Test 1: Increase plotter X
        print("\n" + "-"*60)
        print("TEST 1: Moving plotter in +X direction")
        print("-"*60)
        print("Moving from X=50 to X=100 (plotter X increases)")
        time.sleep(1)
        self.plotter.move_to(100, 50)
        
        print("\nWhat did the plotter do?")
        print("1. Moved RIGHT (toward iPad's right edge)")
        print("2. Moved DOWN (toward iPad's home button/bottom)")
        print("3. Moved LEFT (toward iPad's left edge)")
        print("4. Moved UP (away from iPad's home button)")
        
        x_response = input("\nEnter 1, 2, 3, or 4: ").strip()
        
        self.plotter.move_to(50, 50)
        time.sleep(1)
        
        # Test 2: Increase plotter Y
        print("\n" + "-"*60)
        print("TEST 2: Moving plotter in +Y direction")
        print("-"*60)
        print("Moving from Y=50 to Y=100 (plotter Y increases)")
        time.sleep(1)
        self.plotter.move_to(50, 100)
        
        print("\nWhat did the plotter do?")
        print("1. Moved RIGHT (toward iPad's right edge)")
        print("2. Moved DOWN (toward iPad's home button/bottom)")
        print("3. Moved LEFT (toward iPad's left edge)")
        print("4. Moved UP (away from iPad's home button)")
        
        y_response = input("\nEnter 1, 2, 3, or 4: ").strip()
        
        self.plotter.move_to(50, 50)
        
        # Analyze responses
        print("\n" + "="*60)
        print("AXIS ANALYSIS")
        print("="*60)
        
        # Determine axis configuration
        if x_response == '1' and y_response == '2':
            print("✓ AXES NORMAL")
            print("  Plotter +X → iPad RIGHT")
            print("  Plotter +Y → iPad DOWN")
            self.axes_swapped = False
            self.x_inverted = False
            self.y_inverted = False
            
        elif x_response == '2' and y_response == '1':
            print("⚠ AXES SWAPPED")
            print("  Plotter +X → iPad DOWN")
            print("  Plotter +Y → iPad RIGHT")
            print("  → Will automatically compensate in coordinate mapping")
            self.axes_swapped = True
            self.x_inverted = False
            self.y_inverted = False
            
        elif x_response == '3' and y_response == '2':
            print("⚠ X-AXIS INVERTED")
            print("  Plotter +X → iPad LEFT")
            print("  Plotter +Y → iPad DOWN")
            self.axes_swapped = False
            self.x_inverted = True
            self.y_inverted = False
            
        elif x_response == '1' and y_response == '4':
            print("⚠ Y-AXIS INVERTED")
            print("  Plotter +X → iPad RIGHT")
            print("  Plotter +Y → iPad UP")
            self.axes_swapped = False
            self.x_inverted = False
            self.y_inverted = True
            
        elif x_response == '2' and y_response == '3':
            print("⚠ AXES SWAPPED + Y-AXIS INVERTED")
            print("  Plotter +X → iPad DOWN")
            print("  Plotter +Y → iPad LEFT")
            self.axes_swapped = True
            self.x_inverted = False
            self.y_inverted = True
            
        elif x_response == '4' and y_response == '1':
            print("⚠ AXES SWAPPED + X-AXIS INVERTED")
            print("  Plotter +X → iPad UP")
            print("  Plotter +Y → iPad RIGHT")
            self.axes_swapped = True
            self.x_inverted = True
            self.y_inverted = False
            
        else:
            print("⚠ UNUSUAL CONFIGURATION DETECTED")
            print(f"  Plotter +X response: {x_response}")
            print(f"  Plotter +Y response: {y_response}")
            print("  → Will attempt automatic compensation")
            self.axes_swapped = (x_response == '2' or x_response == '4')
            self.x_inverted = (x_response == '3' or x_response == '4')
            self.y_inverted = (y_response == '4' or y_response == '3')
        
        # Create mapper with appropriate settings
        self.mapper = CoordinateMapper(swap_axes=self.axes_swapped)
        
        print("\n✓ Axis configuration detected and compensated")
        return True
    
    def find_plotter_limits(self):
        """Manually find the plotter's physical limits"""
        print("\n" + "="*60)
        print("STEP 2: FINDING PLOTTER WORKING AREA")
        print("="*60)
        print("We'll move to corner positions to find your working area.")
        print("Make sure iPad will fit within this area!\n")
        
        self.plotter.pen_up()
        self.plotter.move_to(0, 0)
        input("Plotter at origin (0, 0). Press Enter to continue...")
        
        # Test corners with conservative values
        test_positions = [
            (0, 0, "Origin / Home position"),
            (150, 0, "Right edge (X=150)"),
            (150, 200, "Far right corner (X=150, Y=200)"),
            (0, 200, "Left far corner (Y=200)"),
            (75, 100, "Center position")
        ]
        
        positions_found = []
        
        for x, y, description in test_positions:
            print(f"\n--- Testing: {description} ---")
            self.plotter.move_to(x, y)
            
            response = input("Is this position reachable and safe? (y/n): ").lower()
            if response == 'y':
                positions_found.append((x, y, description))
            else:
                print("Position not reachable. Let's adjust...")
                new_x = float(input(f"  Enter safe X value (was {x}): "))
                new_y = float(input(f"  Enter safe Y value (was {y}): "))
                self.plotter.move_to(new_x, new_y)
                confirm = input("  Is this position OK? (y/n): ").lower()
                if confirm == 'y':
                    positions_found.append((new_x, new_y, f"{description} (adjusted)"))
        
        if len(positions_found) >= 4:
            print("\n✓ Found valid working area!")
            x_coords = [p[0] for p in positions_found]
            y_coords = [p[1] for p in positions_found]
            
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)
            
            # Apply inversions if needed
            if self.x_inverted:
                print("⚠ Swapping X bounds due to X-axis inversion")
                x_min, x_max = x_max, x_min
            if self.y_inverted:
                print("⚠ Swapping Y bounds due to Y-axis inversion")
                y_min, y_max = y_max, y_min
            
            print(f"\n📏 Plotter bounds:")
            print(f"   X: {x_min} mm to {x_max} mm")
            print(f"   Y: {y_min} mm to {y_max} mm")
            
            confirm = input("\nSet these as plotter bounds? (y/n): ").lower()
            if confirm == 'y':
                self.mapper.set_plotter_bounds(x_min, x_max, y_min, y_max)
                return True
        
        print("❌ Could not establish valid working area")
        return False
    
    def mark_ipad_corners_portrait(self):
        """Mark the four corners of the iPad game area"""
        print("\n" + "="*60)
        print("STEP 3: MARKING iPAD GAME AREA CORNERS")
        print("="*60)
        print("📱 Ensure iPad is in PORTRAIT mode")
        print("📱 Solitaire game should be displayed\n")
        
        input("Position your iPad under the plotter. Press Enter when ready...")
        
        # Define corners - these are in PLOTTER coordinates
        # The mapper will handle axis swapping automatically
        corners = [
            ("TOP-LEFT", "Where first Ace foundation pile appears", 
             self.mapper.plotter_bounds['x_min'], self.mapper.plotter_bounds['y_min']),
            ("TOP-RIGHT", "Where fourth Ace foundation pile appears",
             self.mapper.plotter_bounds['x_max'], self.mapper.plotter_bounds['y_min']),
            ("BOTTOM-RIGHT", "Bottom right of tableau piles",
             self.mapper.plotter_bounds['x_max'], self.mapper.plotter_bounds['y_max']),
            ("BOTTOM-LEFT", "Bottom left of tableau piles",
             self.mapper.plotter_bounds['x_min'], self.mapper.plotter_bounds['y_max'])
        ]
        
        self.plotter.pen_up()
        
        print("\n🔵 Marking each corner with a small dot")
        if self.axes_swapped:
            print("   (Axis swap compensation active)")
        print()
        
        for name, description, x, y in corners:
            print(f"\n--- {name} Corner ---")
            print(f"    Location: {description}")
            print(f"    Moving to plotter: X={x:.1f}, Y={y:.1f}")
            
            self.plotter.move_to(x, y)
            input("    Press Enter to mark this corner...")
            
            self.plotter.pen_down()
            time.sleep(0.3)
            self.plotter.pen_up()
            
            print(f"    ✓ Marked {name} corner")
        
        print("\n" + "="*60)
        print("✓ ALL CORNERS MARKED!")
        print("="*60)
        print("\n📸 NEXT STEPS:")
        print("1. Take a screenshot of your iPad (Power + Volume Up)")
        print("2. Transfer the screenshot to this computer")
        print("3. Measure pixel coordinates of the marked dots")
    
    def set_ipad_coordinates(self):
        """Manually input iPad pixel coordinates"""
        print("\n" + "="*60)
        print("STEP 4: SET iPAD PIXEL COORDINATES")
        print("="*60)
        print("Enter the pixel coordinates from your screenshot.\n")
        
        try:
            x_min = int(input("  Left edge X-coordinate (pixels): "))
            x_max = int(input("  Right edge X-coordinate (pixels): "))
            y_min = int(input("  Top edge Y-coordinate (pixels): "))
            y_max = int(input("  Bottom edge Y-coordinate (pixels): "))
            
            if x_max <= x_min:
                print("❌ Error: Right edge must be greater than left edge")
                return False
            if y_max <= y_min:
                print("❌ Error: Bottom edge must be greater than top edge")
                return False
            
            width = x_max - x_min
            height = y_max - y_min
            
            print(f"\n📏 Game area dimensions:")
            print(f"   Width: {width} pixels")
            print(f"   Height: {height} pixels")
            print(f"   Aspect ratio: {height/width:.2f}")
            
            if height < width:
                print("⚠ WARNING: Height < Width suggests landscape mode!")
                confirm = input("   Continue anyway? (y/n): ").lower()
                if confirm != 'y':
                    return False
            
            self.mapper.set_ipad_bounds(x_min, x_max, y_min, y_max)
            return True
            
        except ValueError:
            print("❌ Invalid input! Please enter numbers only.")
            return False
    
    def test_calibration(self):
        """Test the calibration by moving to test points"""
        print("\n" + "="*60)
        print("STEP 5: TESTING CALIBRATION")
        print("="*60)
        
        ix_min = self.mapper.ipad_bounds['x_min']
        ix_max = self.mapper.ipad_bounds['x_max']
        iy_min = self.mapper.ipad_bounds['y_min']
        iy_max = self.mapper.ipad_bounds['y_max']
        
        ix_center = (ix_min + ix_max) // 2
        iy_center = (iy_min + iy_max) // 2
        
        test_points = [
            ("Top-left corner", ix_min + 50, iy_min + 50),
            ("Top-right corner", ix_max - 50, iy_min + 50),
            ("Center of screen", ix_center, iy_center),
            ("Bottom-left corner", ix_min + 50, iy_max - 50),
            ("Bottom-right corner", ix_max - 50, iy_max - 50)
        ]
        
        self.plotter.pen_up()
        
        for name, ipad_x, ipad_y in test_points:
            plotter_x, plotter_y = self.mapper.ipad_to_plotter(ipad_x, ipad_y)
            
            print(f"\n--- Test: {name} ---")
            print(f"  iPad: ({ipad_x}, {ipad_y})")
            print(f"  Plotter: ({plotter_x:.2f}, {plotter_y:.2f})")
            
            input("  Press Enter to move...")
            self.plotter.move_to(plotter_x, plotter_y)
            
            mark = input("  Mark this position? (y/n): ").lower()
            if mark == 'y':
                self.plotter.pen_down()
                time.sleep(0.2)
                self.plotter.pen_up()
    
    def run_full_calibration(self):
        """Run the complete smart calibration process"""
        print("="*60)
        print("SMART iPAD SOLITAIRE PLOTTER CALIBRATION")
        print("(Automatic Axis Detection)")
        print("="*60)
        
        # Step 1: Test and detect axis configuration
        if not self.test_axis_directions():
            return False
        
        input("\nPress Enter to continue to Step 2...")
        
        # Step 2: Find plotter limits
        if not self.find_plotter_limits():
            return False
        
        input("\nPress Enter to continue to Step 3...")
        
        # Step 3: Mark iPad corners
        self.mark_ipad_corners_portrait()
        
        input("\nPress Enter when you've measured coordinates...")
        
        # Step 4: Set iPad coordinates
        if not self.set_ipad_coordinates():
            return False
        
        # Step 5: Test mapping
        self.mapper.test_mapping()
        
        # Step 6: Physical test
        test = input("\nRun physical test? (y/n): ").lower()
        if test == 'y':
            self.test_calibration()
        
        print("\n" + "="*60)
        print("✓ CALIBRATION COMPLETE!")
        print("="*60)
        return True
