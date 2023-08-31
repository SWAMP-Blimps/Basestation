
class Blimp:
    def __init__(self, blimp_name):
        # Blimp Name
        self.blimp_name = blimp_name

        # Auto 
        self.auto = False

        # Killed
        self.killed = False

        # Motor Commands
        self.motor_commands = [0, 0, 0, 0]

        # Grabbing
        self.grabbing = False

        # Shooting
        self.shooting = False

        # Target Goal Color
        self.goal_color = 0 # 0: Orange, 1: Yellow

        # Target Color
        self.target_color = 0 # 0: Blue, 1: Red

        # State Machine
        self.state_machine = 0 
        """
        0: searching
        1: approach
        2: catching
        3: caught
        4: goalSearch
        5: approachGoal
        6: scoringStart
        7: shooting
        8: scored
        """
    
    def to_dict(self):
        return {
            "blimp_name": self.blimp_name,
            "auto": self.auto,
            "killed": self.killed,
            "motor_commands": self.motor_commands,
            "grabbing": self.grabbing,
            "shooting": self.shooting,
            "goal_color": self.goal_color,
            "target_color": self.target_color,
            "state_machine": self.state_machine
        }
    
    def update_dict(self, data_dict):
        if "blimp_name" in data_dict:
            self.blimp_name = data_dict["blimp_name"]
        if "auto" in data_dict:
            self.auto = data_dict["auto"]
        if "killed" in data_dict:
            self.killed = data_dict["killed"]
        if "motor_commands" in data_dict:
            self.motorCommands = data_dict["motor_commands"]
        if "grabbing" in data_dict:
            self.grabbing = data_dict["grabbing"]
        if "shooting" in data_dict:
            self.shooting = data_dict["shooting"]
        if "goal_color" in data_dict:
            self.goal_color = data_dict["goal_color"]
        if "target_color" in data_dict:
            self.target_color = data_dict["target_color"]
        if "state_machine" in data_dict:
            self.state_machine = data_dict["state_machine"]