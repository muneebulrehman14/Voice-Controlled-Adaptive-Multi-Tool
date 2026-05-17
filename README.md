# Voice-Controlled Adaptive Multi-Tool

## Overview
This project demonstrates a voice-controlled adaptive multi-tool that can change shape, make fine adjustments, and repair minor damage. The concept combines claytronics, shape memory alloys, nanotechnology, and machine learning.

## Features
- Voice control using J.A.R.V.I.S. AI
- 3D animation in Blender
- Shape transformation (hammer ↔ wrench ↔ sword ↔ screwdriver)
- Self-repair capability
- 85-90% voice recognition accuracy

## Technologies Used
- **Blender** - 3D animation
- **Python** - Voice recognition and AI
- **SpeechRecognition** - Audio processing
- **scikit-learn** - Machine learning classification
- **J.A.R.V.I.S. AI** - Command interpretation

## ⚠️ IMPORTANT: Before Running the Blender Script

The Blender script (`blender_animation.blend` or `.py` file) contains file paths to external 3D models. You **MUST** update these paths to match your own computer.

### Find these lines in the Blender script:

```python
HAMMER_OBJ = "/home/mssocial/Desktop/blend/10293_Hammer_v1_L3.../10293_Hammer_v1_iterations-2.obj"
WRENCH_OBJ = "/home/mssocial/Desktop/blend/Monkey_Wrench_v3_L3.../10299_Monkey-Wrench_v1_L3.obj"
SWORD_OBJ  = "/home/mssocial/Desktop/blend/kp57owlf883k-sword/Sword.obj"
SCREWDRIVER_OBJ = "/home/mssocial/Desktop/blend/10287_Flat_Head_Screwdriver_v3_L2.../10287_Flat_Head_Screwdriver_v2_iterations-2.obj"
COMMAND_FILE = "/home/mssocial/Desktop/jarvis_cmd.txt"

Change them to your own file locations:
HAMMER_OBJ = "C:/YourFolder/your_hammer_model.obj"
WRENCH_OBJ = "C:/YourFolder/your_wrench_model.obj"
SWORD_OBJ  = "C:/YourFolder/your_sword_model.obj"
SCREWDRIVER_OBJ = "C:/YourFolder/your_screwdriver_model.obj"
COMMAND_FILE = "C:/Users/YourName/Desktop/jarvis_cmd.txt"


