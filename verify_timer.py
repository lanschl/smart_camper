import time
import logging
from camper_backend.hardware.heater import HeaterController

# Setup logging
logging.basicConfig(level=logging.INFO)

def verify_timer():
    print("--- Starting Timer Verification ---")
    
    # Initialize controller
    # We use a dummy serial number and log path as we are likely using the mock
    controller = HeaterController(serial_num="TEST_SERIAL", log_path="./test_heater.log")
    
    # Give it a moment to initialize
    time.sleep(1)
    
    # 1. Test turning on with timer
    print("\n[TEST 1] Turning on Power Mode with 5 minute timer...")
    controller.turn_on_heating("power", 5, run_timer_minutes=5)
    
    time.sleep(1)
    state = controller.get_state()
    print(f"State after turn on: Mode={state['mode']}, Status={state['status']}, Timer={state['timer']}")
    
    if state['timer'] == 5 or state['timer'] == 4: # It might tick down immediately depending on timing
        print("✅ SUCCESS: Timer is set correctly.")
    else:
        print(f"❌ FAILURE: Timer is {state['timer']}, expected ~5.")

    # 2. Test turning off
    print("\n[TEST 2] Turning off...")
    controller.shutdown()
    time.sleep(1)
    state = controller.get_state()
    print(f"State after shutdown: Mode={state['mode']}, Status={state['status']}, Timer={state['timer']}")
    
    if state['timer'] is None:
        print("✅ SUCCESS: Timer cleared on shutdown.")
    else:
        print(f"❌ FAILURE: Timer is {state['timer']}, expected None.")

    controller.cleanup()
    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    verify_timer()
