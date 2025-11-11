import time
from plotter_controller import PenPlotter
from CoordinateMapper import CoordinateMapper

class PlotterCalibrator:
    def __init__(self, plotter: PenPlotter, mapper: CoordinateMapper):
        self.plotter = plotter
        self.mapper = mapper
    
    def find_plotter_limits(self):
        """Manually find the plotter's physical limits"""
        print("\n=== FINDING PLOTTER LIMITS ===")
        print("We'll move to corner positions to find your working area.")
        print("Measure where the pencil is positioned at each corner.\n")
        
        # Start at origin
        self.plotter.pen_up()
        #self.plotter.move_to(0, 0)
        input("Plotter at (0, 0). Press Enter to continue...")
        
        # Test corners - adjust these values based on your plotter size
        test_positions = [
            (0, 0, "Bottom-left corner"),
            (225, 0, "Bottom-right corner (adjust X value if needed)"),
            (100, 100, "Top-right corner (adjust X/Y if needed)"),
            (0, 200, "Top-left corner"),
            (100, 100, "Center position")
        ]
        
        positions_found = []
        
        for x, y, description in test_positions:
            self.plotter.move_to(x, y)
            print(f"\nMoved to {description}: X={x}, Y={y}")
            
            response = input("Is this position reachable? (y/n): ").lower()
            if response == 'y':
                positions_found.append((x, y, description))
                
                # Optional: mark position on iPad
                mark = input("Want to mark this position? (y/n): ").lower()
                if mark == 'y':
                    self.plotter.pen_down()
                    time.sleep(0.5)
                    self.plotter.pen_up()
            else:
                print("Adjust the coordinates and try again!")
                break
        
        if len(positions_found) >= 4:
            print("\n✓ Found valid working area!")
            x_coords = [p[0] for p in positions_found[:4]]
            y_coords = [p[1] for p in positions_found[:4]]
            
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)
            
            print(f"Suggested bounds: X({x_min}-{x_max}), Y({y_min}-{y_max})")
            
            confirm = input("Set these as plotter bounds? (y/n): ").lower()
            if confirm == 'y':
                self.mapper.set_plotter_bounds(x_min, x_max, y_min, y_max)
                return True
        
        return False
    
    def mark_ipad_corners(self):
        """Mark the four corners of the iPad game area"""
        print("\n=== MARKING iPAD CORNERS ===")
        print("Place iPad under plotter. We'll mark the game area corners.\n")
        
        corners = [
            ("bottom-left", self.mapper.plotter_bounds['x_min'], self.mapper.plotter_bounds['y_min']),
            ("bottom-right", self.mapper.plotter_bounds['x_max'], self.mapper.plotter_bounds['y_min']),
            ("top-right", self.mapper.plotter_bounds['x_max'], self.mapper.plotter_bounds['y_max']),
            ("top-left", self.mapper.plotter_bounds['x_min'], self.mapper.plotter_bounds['y_max'])
        ]
        
        self.plotter.pen_up()
        
        for name, x, y in corners:
            self.plotter.move_to(x, y)
            input(f"\nMoved to {name} corner. Press Enter to mark...")
            
            # Make a small dot
            self.plotter.pen_down()
            time.sleep(0.3)
            self.plotter.pen_up()
            
            print(f"✓ Marked {name} corner")
        
        print("\n=== NEXT STEP ===")
        print("1. Take a screenshot of your iPad with the marked corners visible")
        print("2. Open the screenshot in an image viewer")
        print("3. Note the pixel coordinates of each marked corner")
        print("4. Note the pixel coordinates of the solitaire game area")
    
    def set_ipad_coordinates(self):
        """Manually input iPad pixel coordinates"""
        print("\n=== SET iPAD COORDINATES ===")
        print("Enter the pixel coordinates from your screenshot.\n")
        
        try:
            x_min = int(input("Game area LEFT edge (x_min in pixels): "))
            x_max = int(input("Game area RIGHT edge (x_max in pixels): "))
            y_min = int(input("Game area TOP edge (y_min in pixels): "))
            y_max = int(input("Game area BOTTOM edge (y_max in pixels): "))
            
            self.mapper.set_ipad_bounds(x_min, x_max, y_min, y_max)
            return True
            
        except ValueError:
            print("Invalid input! Please enter numbers only.")
            return False
    
    def test_calibration(self):
        """Test the calibration by moving to test points"""
        print("\n=== TESTING CALIBRATION ===")
        
        # Test some positions
        test_points = [
            ("Top-left card", self.mapper.ipad_bounds['x_min'] + 100, 
             self.mapper.ipad_bounds['y_min'] + 100),
            ("Center", 
             (self.mapper.ipad_bounds['x_min'] + self.mapper.ipad_bounds['x_max']) // 2,
             (self.mapper.ipad_bounds['y_min'] + self.mapper.ipad_bounds['y_max']) // 2),
            ("Bottom-right", 
             self.mapper.ipad_bounds['x_max'] - 100,
             self.mapper.ipad_bounds['y_max'] - 100)
        ]
        
        self.plotter.pen_up()
        
        for name, ipad_x, ipad_y in test_points:
            plotter_x, plotter_y = self.mapper.ipad_to_plotter(ipad_x, ipad_y)
            
            print(f"\nTest: {name}")
            print(f"  iPad coords: ({ipad_x}, {ipad_y})")
            print(f"  Plotter coords: ({plotter_x:.2f}, {plotter_y:.2f})")
            
            input("Press Enter to move to this position...")
            self.plotter.move_to(plotter_x, plotter_y)
            
            mark = input("Mark this position? (y/n): ").lower()
            if mark == 'y':
                self.plotter.pen_down()
                time.sleep(0.2)
                self.plotter.pen_up()
    
    def run_full_calibration(self):
        """Run the complete calibration process"""
        print("=" * 50)
        print("PLOTTER CALIBRATION WIZARD")
        print("=" * 50)
        
        # Step 1: Find plotter limits
        if not self.find_plotter_limits():
            print("Calibration cancelled.")
            return False
        
        # Step 2: Mark iPad corners
        self.mark_ipad_corners()
        
        input("\nPress Enter when you've taken a screenshot and are ready to continue...")
        
        # Step 3: Set iPad coordinates
        if not self.set_ipad_coordinates():
            print("Calibration cancelled.")
            return False
        
        # Step 4: Test mapping
        self.mapper.test_mapping()
        
        # Step 5: Physical test
        test = input("\nRun physical calibration test? (y/n): ").lower()
        if test == 'y':
            self.test_calibration()
        
        print("\n✓ CALIBRATION COMPLETE!")
        return True