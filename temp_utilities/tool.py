import wmi
import time

def monitor_energy_usage():
    try:
        # Connect to the local machine
        c = wmi.WMI()

        # Attempt to query relevant classes for power usage.
        # Note: Direct, standard WMI classes for detailed, real-time energy
        # consumption (like Wattage) are often restricted or require
        # specific hardware/OS APIs not universally available via standard WMI.
        # A common proxy is checking processor power state or system metrics.

        print("--- Monitoring System Power Metrics via WMI ---")
        print("Note: Detailed energy (Wattage) measurements usually require specialized APIs.")
        print("Attempting to query basic system information and power status...")

        # Querying Win32_Processor for basic usage info
        processor = c.Win32_Processor()
        if processor:
            print("\n[Processor Information]")
            for p in processor:
                print(f"  Model: {p.Name}")
                print(f"  NumberOfCores: {p.NumberOfCores}")
                print(f"  MaxClockSpeed: {p.MaxClockSpeed} MHz")

        # Querying Win32_ComputerSystem for overall system status
        computer = c.Win32_ComputerSystem()
        if computer:
            print("\n[System Information]")
            #print(computer[0])
            print(f"  System Manufacturer: {computer[0].Manufacturer}")
            print(f"  System Model: {computer[0].Model}")
            print(f"  System Power State: {computer[0].PowerState}")

        # Simple loop to simulate monitoring over time
        for i in range(3):
            time.sleep(1)
            print(f"\n[Monitoring cycle {i+1}/3 completed. (Requires elevated privileges for detailed metrics)]")

    except wmi.x_wmi as e:
        print(f"WMI Error: Could not connect or query required classes. Ensure the script is run with Administrator privileges. Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    monitor_energy_usage()