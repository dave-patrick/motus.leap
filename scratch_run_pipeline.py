import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import scheduler
print("Starting API pipeline sequence...")
scheduler.run_pipeline_sequence()
print("API pipeline sequence finished!")
